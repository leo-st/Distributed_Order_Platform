from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/orders"
    log_level: str = "INFO"

    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_consumer_group: str = "payment-service"

    # Mock payment gateway
    payment_min_latency: float = 1.0
    payment_max_latency: float = 5.0
    payment_timeout: float = 4.0
    payment_decline_rate: float = 0.15
    payment_max_retries: int = 3

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 30.0

    # Observability
    otlp_endpoint: str = "http://jaeger:4318/v1/traces"
    metrics_port: int = 8001

    model_config = {"env_file": ".env"}


settings = Settings()
