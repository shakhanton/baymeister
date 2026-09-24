from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://baymeister:baymeister@localhost:5432/scheduling"

    # Порожньо — події пишуться в лог, а копії клієнта й авто не оновлюються.
    rabbitmq_url: str | None = None
    events_exchange: str = "baymeister"
    events_queue: str = "scheduling.copies"

    # Сусідні сервіси напряму, всередині мережі. Заголовки X-User-* йдуть далі.
    customers_url: str = "http://localhost:8001"
    vehicles_url: str = "http://localhost:8003"
    peers_timeout_seconds: float = 5.0

    port: int = 8005
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
