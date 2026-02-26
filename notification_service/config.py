from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_level: str = "INFO"

    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_consumer_group: str = "notification-service"

    # Observability
    otlp_endpoint: str = "http://jaeger:4318/v1/traces"
    metrics_port: int = 8002

    model_config = {"env_file": ".env"}


settings = Settings()
