from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://baymeister:baymeister@localhost:5432/inventory"

    # Порожньо — події пишуться в лог, а резерви й списання з нарядів не приходять.
    rabbitmq_url: str | None = None
    events_exchange: str = "baymeister"
    events_queue: str = "inventory.events"

    # catalog напряму, всередині мережі: перевірити деталь при приході.
    catalog_url: str = "http://localhost:8004"
    peers_timeout_seconds: float = 5.0

    port: int = 8007
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
