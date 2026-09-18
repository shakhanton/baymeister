from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://baymeister:baymeister@localhost:5432/customers"

    # Порожньо — події пишуться в лог. Так блок піднімається без RabbitMQ.
    rabbitmq_url: str | None = None
    events_exchange: str = "baymeister"

    port: int = 8001
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
