# Gateway Service

This FastAPI gateway exposes the `/simulateTicket` endpoint, which publishes `ticket.created` events to Kafka using the `ticketId` as the key. Prometheus metrics are available at `/metrics`.

## Run locally with Docker Compose

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d --build
```

## Health and metrics checks

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/metrics | head
```

## Send events

Custom payload with idempotency key:

```bash
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
```

Automatically generated payload:

```bash
curl -X POST http://localhost:8000/simulateTicket
```

## Consume from Kafka

```bash
docker compose exec kafka bash -lc \
'kafka-console-consumer --bootstrap-server localhost:9092 --topic ticket.created --from-beginning --timeout-ms 3000'
```
