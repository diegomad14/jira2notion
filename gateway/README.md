# Gateway Service

The gateway is a FastAPI service that can simulate ticket creation events and publish them into Kafka.
It also exposes Prometheus metrics for observability.

## Endpoints

- `GET /health` – Simple health probe returning the service status.
- `GET /metrics` – Prometheus metrics in the text exposition format.
- `POST /simulateTicket` – Publish a `ticket.created` event to Kafka. The request body is optional; if it is missing the service generates a synthetic payload.

### Request headers

- `Content-Type: application/json` (when sending a custom body).
- `X-Idempotency-Key` (optional). When present the same key prevents duplicate events. If omitted, the `ticketId` is used as the idempotency key.

### Request body schema

```json
{
  "ticketId": "AIMA-49-DEMO",
  "source": "simulator",
  "projectKey": "AIMA",
  "summary": "Cannot log in to JSM",
  "description": "401 error when using SSO",
  "reporter": "diego.martinez@rappi.com",
  "priority": "Medium",
  "lang": "en",
  "createdAt": "2024-05-14T16:00:00Z"
}
```

All fields are optional; unspecified values are filled with defaults. The service always adds `eventType="ticket.created"` and `version="v1"` before sending the payload to Kafka.

## Running locally with Docker Compose

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
2. Build and start the stack:
   ```bash
   docker compose -f infra/docker-compose.yml up -d --build
   ```

Kafka, Zookeeper, the gateway, and Prometheus will be started on the shared `aimnet` network.

## Smoke tests

```bash
# Health and metrics
curl -s http://localhost:8000/health
curl -s http://localhost:8000/metrics | head

# Send with custom payload and idempotency key
curl -X POST http://localhost:8000/simulateTicket \
  -H 'Content-Type: application/json' \
  -H 'X-Idempotency-Key: demo-001' \
  -d '{
    "ticketId": "AIMA-49-DEMO",
    "summary": "Cannot log in to JSM",
    "description": "401 error when using SSO",
    "priority": "High",
    "reporter": "diego.martinez@rappi.com",
    "projectKey": "AIMA",
    "lang": "en"
  }'

# Send with no body (auto-generated)
curl -X POST http://localhost:8000/simulateTicket

# Consume from Kafka
# (press Ctrl+C once a message is shown)
docker compose -f infra/docker-compose.yml exec kafka bash -lc \
  'kafka-console-consumer --bootstrap-server localhost:9092 --topic ticket.created --from-beginning --timeout-ms 3000'
```

Prometheus metrics can be inspected at http://localhost:9090 once the stack is up.
