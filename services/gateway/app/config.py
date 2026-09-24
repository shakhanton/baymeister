from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Блок → адреса сервісу. Перший сегмент шляху після /api і є ключем:
    # /api/customers/… → customers. Новий блок — новий рядок тут, код не змінюється.
    # У змінній оточення задається JSON: UPSTREAMS='{"customers": "http://customers:8001"}'
    upstreams: dict[str, str] = {
        "identity": "http://localhost:8002",
        "customers": "http://localhost:8001",
        "vehicles": "http://localhost:8003",
    }

    # Звідки брати публічні ключі для перевірки токенів.
    jwks_url: str = "http://localhost:8002/identity/.well-known/jwks.json"
    jwt_issuer: str = "baymeister-identity"
    # Не частіше ніж раз на стільки секунд перечитувати JWKS через невідомий kid —
    # інакше потік токенів зі сміттєвим kid перетворюється на DoS для identity.
    jwks_refresh_cooldown_seconds: float = 5.0

    upstream_timeout_seconds: float = 30.0

    port: int = 8000
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
