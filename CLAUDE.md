# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A food ordering platform built iteratively across multiple phases to explore distributed systems engineering. See `README.md` for the full roadmap.

**Current phase: Phase 2 — Event-Driven Architecture**
Three services (API, Payment, Notification) connected via Kafka (KRaft), sharing a PostgreSQL database.

## Common Commands

```bash
# Start all services (app + db + kafka + payment_service + notification_service + pgadmin)
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

## Architecture (Phase 2)

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
│   └── request_id.py    # Injects X-Request-ID into every request/response
└── utils/
    └── logging.py       # JSON structured logging via python-json-logger

payment_service/            # Kafka consumer + payment logic
├── Dockerfile
├── config.py, database.py, models.py
├── payment_processor.py  # Mock payment gateway + CircuitBreaker + manual retry
├── consumer.py           # at-least-once + idempotency + DLQ
├── main.py
└── utils/logging.py

notification_service/       # Kafka consumer, logs only
├── Dockerfile
├── config.py, consumer.py, main.py
└── utils/logging.py

shared/                     # Event Pydantic schemas (copied into each container)
├── __init__.py
└── events.py               # OrderPlacedEvent, PaymentCompletedEvent, EventBase
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

**Shared PostgreSQL DB**: Both `app` and `payment_service` write to the same DB — intentional for Phase 2. Phase 3 would introduce per-service schemas.

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
| PostgreSQL | localhost:5432 (postgres/postgres) |
