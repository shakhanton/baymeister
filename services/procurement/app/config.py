from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://baymeister:baymeister@localhost:5432/procurement"

    # Порожньо — події пишуться в лог: склад не отримує приходів, а сигнали
    # «мало на складі» не доходять.
    rabbitmq_url: str | None = None
    events_exchange: str = "baymeister"
    events_queue: str = "procurement.events"

    # catalog напряму, всередині мережі: деталь для рядка замовлення.
    catalog_url: str = "http://localhost:8004"
    peers_timeout_seconds: float = 5.0

    # Рік у номері замовлення — за місцевим часом сервісу, не UTC.
    business_timezone: str = "Europe/Kyiv"

    port: int = 8008
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
