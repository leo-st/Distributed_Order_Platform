"""
Mock payment gateway with:
  - Random latency (simulates real network I/O)
  - Random failures: non-retryable declines + retryable timeouts
  - Manual exponential-backoff retry loop (educational, not tenacity)
  - Custom circuit breaker (fail-fast when gateway is consistently down)
"""

import asyncio
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from payment_service.config import settings
from payment_service.metrics import CIRCUIT_STATE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PaymentError(Exception):
    """Base class for payment errors."""


class PaymentDeclinedError(PaymentError):
    """Definitively declined by the gateway — do not retry."""


class PaymentTimeoutError(PaymentError):
    """Gateway timed out — transient, safe to retry."""


class CircuitBreakerOpenError(PaymentError):
    """Circuit breaker is open — fail fast without calling the gateway."""


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


_STATE_GAUGE_VALUES = {
    CircuitState.CLOSED: 0,
    CircuitState.HALF_OPEN: 1,
    CircuitState.OPEN: 2,
}


@dataclass
class CircuitBreaker:
    failure_threshold: int
    recovery_timeout: float

    _failures: int = field(default=0, init=False, repr=False)
    _last_failure_time: float | None = field(default=None, init=False, repr=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)

    @property
    def state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and self._last_failure_time is not None
            and time.monotonic() - self._last_failure_time >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            CIRCUIT_STATE.set(_STATE_GAUGE_VALUES[CircuitState.HALF_OPEN])
            logger.info("Circuit breaker transitioned to HALF_OPEN")
        return self._state

    def allow_request(self) -> bool:
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED
        CIRCUIT_STATE.set(_STATE_GAUGE_VALUES[CircuitState.CLOSED])
        logger.debug("Circuit breaker: success recorded, state=CLOSED")

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._failures >= self.failure_threshold and self._state != CircuitState.OPEN:
            self._state = CircuitState.OPEN
            CIRCUIT_STATE.set(_STATE_GAUGE_VALUES[CircuitState.OPEN])
            logger.warning(
                "Circuit breaker OPENED after %d consecutive failures",
                self._failures,
            )


_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout=settings.circuit_breaker_recovery_timeout,
)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class PaymentResult:
    success: bool
    attempt_count: int
    processing_time_ms: int
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Internal gateway call
# ---------------------------------------------------------------------------


async def _call_gateway(order_id: uuid.UUID, amount: float) -> None:
    """
    Simulates a real payment gateway:
      - Adds random latency between min and max configured values.
      - Times out if latency exceeds the configured timeout.
      - Has a configured probability of declining the payment outright.
    """
    processing_time = random.uniform(settings.payment_min_latency, settings.payment_max_latency)
    logger.debug(
        "Calling payment gateway",
        extra={"order_id": str(order_id), "simulated_latency_s": round(processing_time, 2)},
    )

    try:
        await asyncio.wait_for(asyncio.sleep(processing_time), timeout=settings.payment_timeout)
    except asyncio.TimeoutError:
        raise PaymentTimeoutError(
            f"Gateway did not respond within {settings.payment_timeout}s"
        )

    if random.random() < settings.payment_decline_rate:
        raise PaymentDeclinedError("Insufficient funds")


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def process_payment(
    order_id: uuid.UUID,
    amount: float,
    request_id: str,
) -> PaymentResult:
    """
    Attempt payment with exponential-backoff retries on transient failures.
    Circuit breaker short-circuits when the gateway is repeatedly failing.

    Always returns a PaymentResult — never raises an exception to the caller.
    """
    if not _circuit_breaker.allow_request():
        logger.warning(
            "Circuit breaker OPEN — rejecting payment without calling gateway",
            extra={"order_id": str(order_id), "request_id": request_id},
        )
        return PaymentResult(
            success=False,
            attempt_count=0,
            processing_time_ms=0,
            error_message="Payment service unavailable (circuit breaker open)",
        )

    start = time.monotonic()
    last_error: str | None = None
    attempt = 0

    for attempt in range(1, settings.payment_max_retries + 1):
        logger.info(
            "Payment attempt %d/%d",
            attempt,
            settings.payment_max_retries,
            extra={
                "order_id": str(order_id),
                "request_id": request_id,
                "amount": amount,
                "attempt": attempt,
            },
        )

        try:
            await _call_gateway(order_id, amount)

            elapsed_ms = int((time.monotonic() - start) * 1000)
            _circuit_breaker.record_success()
            logger.info(
                "Payment succeeded",
                extra={
                    "order_id": str(order_id),
                    "request_id": request_id,
                    "attempt": attempt,
                    "processing_time_ms": elapsed_ms,
                },
            )
            return PaymentResult(
                success=True,
                attempt_count=attempt,
                processing_time_ms=elapsed_ms,
            )

        except PaymentDeclinedError as exc:
            # Non-retryable: log and bail out immediately
            _circuit_breaker.record_failure()
            last_error = str(exc)
            logger.warning(
                "Payment declined (non-retryable) — aborting",
                extra={
                    "order_id": str(order_id),
                    "request_id": request_id,
                    "error": last_error,
                },
            )
            break

        except PaymentTimeoutError as exc:
            # Retryable: back off and try again if attempts remain
            _circuit_breaker.record_failure()
            last_error = str(exc)
            logger.warning(
                "Payment timed out on attempt %d",
                attempt,
                extra={
                    "order_id": str(order_id),
                    "request_id": request_id,
                    "error": last_error,
                },
            )
            if attempt < settings.payment_max_retries:
                backoff_seconds = 2 ** (attempt - 1)  # 1s, 2s, 4s, …
                logger.info(
                    "Retrying payment in %ds",
                    backoff_seconds,
                    extra={"order_id": str(order_id), "backoff_s": backoff_seconds},
                )
                await asyncio.sleep(backoff_seconds)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.error(
        "Payment failed after %d attempt(s)",
        attempt,
        extra={
            "order_id": str(order_id),
            "request_id": request_id,
            "attempt_count": attempt,
            "error": last_error,
            "processing_time_ms": elapsed_ms,
        },
    )
    return PaymentResult(
        success=False,
        attempt_count=attempt,
        processing_time_ms=elapsed_ms,
        error_message=last_error,
    )
