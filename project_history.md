# Project History

Incremental changelog — updated on every commit. Load this file at session start instead of re-explaining the project.

---

## Current State

**Phase**: Phase 2 — Event-Driven Architecture (complete)
**Stack**: FastAPI · asyncpg · SQLAlchemy 2.x (async) · PostgreSQL 16 · Kafka (KRaft, apache/kafka) · aiokafka · Docker Compose · Poetry
**Services**: `app` (API), `payment_service` (Kafka consumer), `notification_service` (Kafka consumer)
**Endpoints**: `POST /orders`, `GET /orders/{order_id}`, `GET /health`, `GET /docs`

---

## Changelog

### 2026-02-25 — Fix: atomic DB write in payment_service consumer

**Commits**: `2611ce9`

- Crash between `db.add(pa)` and `db.commit()` left `PaymentAttempt` unwritten, causing idempotency check to miss it on restart and re-charge the payment gateway
- Fix: fetch `Order` before creating `PaymentAttempt` so both writes land in a single `db.commit()` — either both succeed or neither does

### 2026-02-25 — Phase 2: event-driven architecture with Kafka

**Commits**: `48642e9`

- Split monolith into three services: `app` (API), `payment_service`, `notification_service`, connected via Kafka (KRaft, `apache/kafka`)
- `POST /orders` now returns 201 immediately with `status=processing`; payment runs asynchronously in `payment_service`
- `payment_service` consumes `order.placed`, processes payment, updates DB, publishes `payment.completed`; idempotency check prevents duplicate processing on replay; unprocessable messages forwarded to `payment.dlq`
- `notification_service` consumes `payment.completed` and logs a structured notification
- Added `shared/events.py` with Pydantic v2 event schemas (`OrderPlacedEvent`, `PaymentCompletedEvent`) copied into each container at build time
- Removed pgadmin from Docker Compose (replaced by local DBeaver); switched Kafka image from bitnami to `apache/kafka` with correct healthcheck path (`/opt/kafka/bin/kafka-topics.sh`)

### 2026-02-24 — Phase 1 scaffold complete

**Commits**: `2f91eb6` → `7ad6289`

What was built:
- Full FastAPI app scaffolded under `app/` (see `CLAUDE.md` for directory tree)
- Async SQLAlchemy engine with `asyncpg`; all queries use `selectinload()` — no lazy loading
- `MenuItem`, `Order`, `OrderItem`, `PaymentAttempt` ORM models
- `POST /orders` creates an order, runs mock payment with retries + circuit breaker, always returns HTTP 201 (payment outcome in `status` field)
- `GET /orders/{order_id}` fetches order with items and payment attempt
- Custom `CircuitBreaker` dataclass in `payment_service.py` (intentionally readable, no external library)
- Manual retry loop (not tenacity) for educational clarity
- One `PaymentAttempt` record per order, written after all retry attempts complete
- Menu items seeded in FastAPI lifespan startup (`seed_menu_items()`) if table is empty
- `X-Request-ID` middleware injects request ID into every request/response
- JSON structured logging via `python-json-logger`
- Switched from pip to **Poetry** for dependency management
- VSCode debug config + Pylance pointed at Poetry venv
- pgAdmin available at `:5050` (admin@admin.com / admin)

---

<!-- Add new entries above this line, newest first. Format:
### YYYY-MM-DD — short description
**Commits**: `hash` (or hash range)
What changed and why (2-6 bullet points).
-->
