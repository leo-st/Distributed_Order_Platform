# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A food ordering platform built iteratively across multiple phases to explore distributed systems engineering. See `README.md` for the full roadmap.

**Current phase: Phase 1 — Resilient Monolith**
Single FastAPI service + PostgreSQL, running via Docker Compose.

## Common Commands

```bash
# Start all services (app + db + pgadmin)
docker compose up --build

# Start in background
docker compose up -d --build

# View app logs
docker compose logs -f app

# Stop everything
docker compose down

# Wipe database and restart fresh
docker compose down -v && docker compose up --build

# Run a one-off command inside the app container (WORKDIR is /code)
docker compose exec app python -c "..."
```

## Architecture (Phase 1)

```
app/
├── main.py              # FastAPI app, lifespan (create tables + seed), middleware
├── config.py            # Settings via pydantic-settings (env vars)
├── database.py          # Async SQLAlchemy engine + AsyncSession + Base
├── models/              # SQLAlchemy ORM models
│   ├── menu_item.py     # MenuItem
│   ├── order.py         # Order, OrderItem, OrderStatus enum
│   └── payment.py       # PaymentAttempt, PaymentStatus enum
├── schemas/             # Pydantic request/response models
│   ├── order.py         # OrderCreate, OrderResponse, etc.
│   └── menu_item.py     # MenuItemResponse
├── routers/
│   └── orders.py        # POST /orders, GET /orders/{id}
├── services/
│   ├── payment_service.py  # Mock payment gateway + CircuitBreaker + manual retry
│   └── order_service.py    # Order business logic + seed_menu_items()
├── middleware/
│   └── request_id.py    # Injects X-Request-ID into every request/response
└── utils/
    └── logging.py       # JSON structured logging via python-json-logger
```

## Key Design Decisions

**Async throughout**: Uses `sqlalchemy[asyncio]` + `asyncpg`. All DB queries use explicit `selectinload()` — never rely on lazy loading in async context.

**Payment service**: `payment_service.py` is intentionally unreliable (configurable failure rate, latency range, timeout). The `CircuitBreaker` class is a custom implementation (not a library) to keep the logic visible. Manual retry loop (not tenacity) for the same reason — educational clarity over brevity.

**One PaymentAttempt record per order**: Created after all retry attempts complete. Contains final status, total attempt count, total elapsed time, and error message.

**Response design**: `POST /orders` always returns HTTP 201 with the full `OrderResponse`. Payment success/failure is expressed in the `status` field (`completed` vs `failed`) and `payment_successful` bool — not via HTTP error codes.

**Seeding**: Menu items are seeded in the FastAPI lifespan startup event (`seed_menu_items()`), only if the `menu_items` table is empty.

## Environment Variables

Configured in `.env` (see `.env.example`). Key ones:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/orders` | Async DB connection |
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
| pgAdmin | http://localhost:5050 (admin@admin.com / admin) |
| PostgreSQL | localhost:5432 (postgres/postgres) |
