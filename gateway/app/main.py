import json
import os
import time
import uuid
from typing import Optional

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
TOPIC = os.getenv("TICKET_TOPIC", "ticket.created")
SERVICE_NAME = os.getenv("SERVICE_NAME", "gateway")
PORT = int(os.getenv("GATEWAY_PORT", "8000"))

app = FastAPI(title="AIM Agent Gateway")

# Prometheus metrics
events_counter = Counter(
    "gateway_events_produced_total",
    "Total number of Kafka events produced by the gateway",
    ["topic", "result"],
)
latency_hist = Histogram(
    "gateway_kafka_produce_latency_seconds",
    "Kafka produce latency in seconds",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# Simple in-memory idempotency cache (prototype use only)
SEEN_IDS = set()
MAX_SEEN = 5000


class TicketPayload(BaseModel):
    ticketId: Optional[str] = Field(None, description="Unique ticket identifier")
    source: str = Field(default="simulator")
    projectKey: str = Field(default="AIMA")
    summary: str = Field(default="Example: Menu not loading")
    description: str = Field(default="User reports a timeout when loading the menu.")
    reporter: str = Field(default="diego.martinez@rappi.com")
    priority: str = Field(default="Medium")
    lang: str = Field(default="en")
    createdAt: Optional[str] = None  # ISO8601 timestamp


producer: Optional[AIOKafkaProducer] = None


@app.on_event("startup")
async def on_startup():
    """Initialize Kafka producer on startup."""
    global producer
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
    )
    await producer.start()


@app.on_event("shutdown")
async def on_shutdown():
    """Stop Kafka producer gracefully."""
    if producer:
        await producer.stop()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    """Expose Prometheus metrics."""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/simulateTicket")
async def simulate_ticket(
    body: Optional[TicketPayload] = None,
    x_idempotency_key: Optional[str] = Header(default=None),
):
    """
    Simulate or create a ticket and publish a 'ticket.created' event to Kafka.
    Idempotency is handled using 'X-Idempotency-Key' header or 'ticketId' field.
    """
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if body is None:
        body = TicketPayload()
    if not body.ticketId:
        body.ticketId = f"AIMA-{uuid.uuid4().hex[:8]}"
    if not body.createdAt:
        body.createdAt = now_iso

    idem_key = x_idempotency_key or body.ticketId
    if idem_key in SEEN_IDS:
        return {"status": "duplicated", "ticketId": body.ticketId, "topic": TOPIC}
    if len(SEEN_IDS) > MAX_SEEN:
        SEEN_IDS.clear()
    SEEN_IDS.add(idem_key)

    event = body.model_dump()
    event["eventType"] = "ticket.created"
    event["version"] = "v1"

    start = time.perf_counter()
    try:
        await producer.send_and_wait(TOPIC, key=body.ticketId, value=event)
        latency_hist.observe(time.perf_counter() - start)
        events_counter.labels(topic=TOPIC, result="ok").inc()
        return {
            "status": "ok",
            "ticketId": body.ticketId,
            "topic": TOPIC,
            "sentAt": now_iso,
            "payload": event,
        }
    except Exception as exc:  # pylint: disable=broad-except
        latency_hist.observe(time.perf_counter() - start)
        events_counter.labels(topic=TOPIC, result="error").inc()
        return {"status": "error", "error": str(exc)}
