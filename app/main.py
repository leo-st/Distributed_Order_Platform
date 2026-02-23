import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import Base, engine
from app.middleware.request_id import RequestIDMiddleware
from app.routers import orders
from app.services.order_service import seed_menu_items
from app.utils.logging import setup_logging

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — creating database tables")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_menu_items()
    logger.info("Startup complete")
    yield
    logger.info("Shutting down")
    await engine.dispose()


app = FastAPI(
    title="Food Ordering Platform",
    description="Phase 1 — Resilient Monolith",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.include_router(orders.router, prefix="/orders", tags=["orders"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
