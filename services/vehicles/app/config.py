from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://baymeister:baymeister@localhost:5432/vehicles"

    # Порожньо — події пишуться в лог, а копія власника не оновлюється.
    # Так блок піднімається без RabbitMQ.
    rabbitmq_url: str | None = None
    events_exchange: str = "baymeister"
    # Власна черга блоку: переживає перезапуск сервісу, події не губляться.
    events_queue: str = "vehicles.customer-events"

    # Сервіс customers напряму, всередині мережі, — не через gateway: запит
    # уже пройшов gateway, і заголовки X-User-* передаються далі як є.
    customers_url: str = "http://localhost:8001"
    customers_timeout_seconds: float = 5.0

    port: int = 8003
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
