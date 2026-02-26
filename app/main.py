import logging
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from prometheus_client import make_asgi_app

from app.config import settings
from app.database import Base, engine
from app.middleware.metrics import MetricsMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.routers import orders
from app.services.order_service import seed_menu_items
from app.utils.logging import setup_logging
from shared.tracing import setup_tracing

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

setup_tracing("app", settings.otlp_endpoint)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — creating database tables")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

    await seed_menu_items()

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        enable_idempotence=True,
    )
    await producer.start()
    app.state.kafka_producer = producer
    logger.info("Startup complete")

    yield

    await producer.stop()
    await engine.dispose()
    logger.info("Shutting down")


app = FastAPI(
    title="Food Ordering Platform",
    description="Phase 3 — Observability",
    version="3.0.0",
    lifespan=lifespan,
)

FastAPIInstrumentor.instrument_app(app)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestIDMiddleware)
app.include_router(orders.router, prefix="/orders", tags=["orders"])

# Expose Prometheus metrics at /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
