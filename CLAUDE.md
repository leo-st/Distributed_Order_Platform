# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A food ordering platform built iteratively across multiple phases to explore distributed systems engineering. See `README.md` for the full roadmap.

**Current phase: Phase 3 — Observability**
Three services with full observability: Prometheus metrics, OpenTelemetry distributed tracing (Jaeger), and Grafana dashboards.

## Common Commands

```bash
# Start all services (app + db + kafka + payment_service + notification_service + jaeger + prometheus + grafana)
docker compose up --build

# Start in background
docker compose up -d --build

# View logs for all event-driven services
docker compose logs -f app payment_service notification_service

# Stop everything
docker compose down

# Wipe database + kafka data and restart fresh
docker compose down -v && docker compose up --build

# Run a one-off command inside the app container (WORKDIR is /code)
docker compose exec app python -c "..."
```

## Architecture (Phase 3)

```
Event flow:
  POST /orders
    → app: persist Order (PROCESSING) → publish order.placed → return 201 immediately
    → payment_service: consume order.placed → process payment → update DB → publish payment.completed
    → notification_service: consume payment.completed → log structured notification

Directory layout:
app/                        # API Service
├── main.py              # FastAPI app, lifespan (DB + Kafka producer init), middleware
├── config.py            # Settings via pydantic-settings (env vars)
├── database.py          # Async SQLAlchemy engine + AsyncSession + Base
├── models/              # SQLAlchemy ORM models (source of truth for schema)
│   ├── menu_item.py     # MenuItem
│   ├── order.py         # Order, OrderItem, OrderStatus enum
│   └── payment.py       # PaymentAttempt, PaymentStatus enum
├── schemas/             # Pydantic request/response models
│   ├── order.py         # OrderCreate, OrderResponse, etc.
│   └── menu_item.py     # MenuItemResponse
├── routers/
│   └── orders.py        # POST /orders, GET /orders/{id}
├── services/
│   └── order_service.py    # Order business logic, publishes order.placed
├── middleware/
│   ├── request_id.py    # Injects X-Request-ID into every request/response
│   └── metrics.py       # Prometheus HTTP request counter + latency histogram
└── utils/
    └── logging.py       # JSON structured logging via python-json-logger

payment_service/            # Kafka consumer + payment logic
├── Dockerfile
├── config.py, database.py, models.py
├── payment_processor.py  # Mock payment gateway + CircuitBreaker + manual retry + CIRCUIT_STATE gauge
├── consumer.py           # at-least-once + idempotency + DLQ + OTel trace extraction
├── metrics.py            # MESSAGES_CONSUMED, PROCESSING_TIME, PAYMENT_OUTCOMES, CIRCUIT_STATE
├── main.py               # starts prometheus_client.start_http_server(8001) + OTel setup
└── utils/logging.py

notification_service/       # Kafka consumer, logs only
├── Dockerfile
├── config.py, consumer.py, main.py
├── metrics.py            # NOTIFICATIONS counter
└── utils/logging.py      # main.py starts prometheus_client.start_http_server(8002)

shared/                     # Event schemas + tracing helper (copied into each container)
├── __init__.py
├── events.py               # OrderPlacedEvent, PaymentCompletedEvent, EventBase
└── tracing.py              # setup_tracing(service_name, otlp_endpoint) — OTel init

monitoring/                 # Infra config (not mounted into app containers)
├── prometheus.yml          # scrape targets: app:8000, payment_service:8001, notification_service:8002
└── grafana/
    ├── provisioning/
    │   ├── datasources/prometheus.yml   # auto-register Prometheus data source
    │   └── dashboards/dashboards.yml    # load JSON dashboards from /etc/grafana/dashboards
    └── dashboards/platform.json         # pre-built dashboard (orders rate, latency, payment outcomes, circuit breaker)
```

## Kafka Topics

| Topic | Producer | Consumer | Purpose |
|---|---|---|---|
| `order.placed` | API Service | Payment Service | New order ready for payment |
| `payment.completed` | Payment Service | Notification Service | Payment result |
| `payment.dlq` | Payment Service | (manual inspection) | Unprocessable messages |

Topics are auto-created on first use (`KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE: "true"`).

## Key Design Decisions

**Async throughout**: Uses `sqlalchemy[asyncio]` + `asyncpg`. All DB queries use explicit `selectinload()` — never rely on lazy loading in async context.

**`POST /orders` returns immediately**: Status is `PROCESSING`, `payment_attempts` is `[]`. Poll `GET /orders/{id}` until status changes to `completed` or `failed`.

**At-least-once delivery**: `enable_auto_commit=False` on payment_service consumer. Offset committed only after successful DB write + downstream publish. On restart, resumes from last committed offset.

**Idempotency**: Before processing, payment_service checks if a `PaymentAttempt` already exists for the `order_id`. If yes, skips (safe to replay messages).

**DLQ**: Unparseable or fatally broken messages are forwarded to `payment.dlq` and offset is committed (avoids poison-pill loop).

**Idempotent producers**: `enable_idempotence=True` on all producers prevents duplicate messages from broker-side retried sends.

**`send_and_wait`**: Awaits broker ack before returning — ensures no silent message loss.

**Correlation ID**: `X-Request-ID` from HTTP middleware flows through all events as `correlation_id`.

**Shared PostgreSQL DB**: Both `app` and `payment_service` write to the same DB — intentional for this phase.

**OTel trace propagation via Kafka headers**: `inject()` writes W3C `traceparent` header into Kafka message headers; `extract()` in consumers recovers the context. This links HTTP → Kafka publish → Kafka consume spans in Jaeger.

**Metrics servers on 8001/8002**: `payment_service` and `notification_service` use `prometheus_client.start_http_server()` (stdlib thread), not FastAPI. The `app` service exposes `/metrics` as a mounted ASGI sub-app.

**Soft Jaeger dependency**: Services add `jaeger: condition: service_started` in `depends_on` but do not wait for health. `BatchSpanProcessor` queues spans and drops them if Jaeger is unreachable.

**Payment logic**: `payment_processor.py` is intentionally unreliable (configurable failure rate, latency, timeout). `CircuitBreaker` is a custom implementation — educational clarity over brevity.

**One PaymentAttempt record per order**: Created after all retry attempts complete. Contains final status, total attempt count, total elapsed time, and error message.

## Environment Variables

Configured in `.env` (see `.env.example`). Key ones:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/orders` | Async DB connection |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker address |
| `PAYMENT_MIN_LATENCY` | `1.0` | Mock payment min delay (s) |
| `PAYMENT_MAX_LATENCY` | `5.0` | Mock payment max delay (s) |
| `PAYMENT_TIMEOUT` | `4.0` | Timeout before treating as transient failure |
| `PAYMENT_DECLINE_RATE` | `0.15` | Probability of non-retryable decline |
| `PAYMENT_MAX_RETRIES` | `3` | Max retry attempts on timeout |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before circuit opens |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `30` | Seconds before trying half-open |
| `OTLP_ENDPOINT` | `http://jaeger:4318/v1/traces` | OTLP HTTP exporter endpoint |

## Project History Log

`project_history.md` in the repo root is a running changelog. **Update it on every commit** — add a new entry at the top of the Changelog section with:

- Date, short description, commit hash(es)
- 2–6 bullet points summarising what changed and why

This file is the fastest way to get up to speed in a new session. Reference it instead of re-explaining the project.

## Accessing Services Locally

| Service | URL |
|---|---|
| FastAPI app | http://localhost:8000 |
| Interactive docs | http://localhost:8000/docs |
| App metrics | http://localhost:8000/metrics |
| Payment metrics | http://localhost:8001 |
| Notification metrics | http://localhost:8002 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / admin) |
| Jaeger UI | http://localhost:16686 |
| PostgreSQL | localhost:5432 (postgres/postgres) |
