from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/orders"
    log_level: str = "INFO"

    # Mock payment gateway
    payment_min_latency: float = 1.0
    payment_max_latency: float = 5.0
    payment_timeout: float = 4.0
    payment_decline_rate: float = 0.15
    payment_max_retries: int = 3

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 30.0

    model_config = {"env_file": ".env"}


settings = Settings()
