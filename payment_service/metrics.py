from prometheus_client import Counter, Gauge, Histogram

MESSAGES_CONSUMED = Counter(
    "payment_messages_consumed_total",
    "Kafka messages consumed by payment service",
    ["status"],  # processed | skipped | dlq
)

PROCESSING_TIME = Histogram(
    "payment_processing_duration_seconds",
    "End-to-end payment processing time",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
)

PAYMENT_OUTCOMES = Counter(
    "payment_outcomes_total",
    "Payment outcomes by type",
    ["outcome"],  # success | failed | declined | circuit_open
)

CIRCUIT_STATE = Gauge(
    "payment_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
)
