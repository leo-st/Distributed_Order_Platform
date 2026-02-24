from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_level: str = "INFO"

    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_consumer_group: str = "notification-service"

    model_config = {"env_file": ".env"}


settings = Settings()
