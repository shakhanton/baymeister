"""
Синхронне читання з блоку customers.

Потрібне в одному місці: коли автомобіль створюють або продають, треба
переконатися, що клієнт існує, і взяти його імʼя й телефон. Далі копія
оновлюється подіями, без запитів.

Запит іде від імені того самого користувача: заголовки X-User-* передаються
далі, тож customers сам вирішує, чи можна цьому користувачу бачити клієнта.
"""

import uuid
from dataclasses import dataclass

import httpx

from app.config import get_settings

FORWARDED_HEADERS = ("x-user-id", "x-user-role", "x-user-permissions", "x-request-id")


@dataclass(frozen=True)
class CustomerSnapshot:
    id: uuid.UUID
    name: str
    phone: str


class CustomerNotFound(Exception):
    pass


class CustomerForbidden(Exception):
    pass


class CustomersUnavailable(Exception):
    pass


class CustomersClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def get(self, customer_id: uuid.UUID, headers: dict[str, str]) -> CustomerSnapshot:
        forwarded = {k: v for k, v in headers.items() if k.lower() in FORWARDED_HEADERS}
        try:
            response = await self._http.get(
                f"{self._base_url}/customers/{customer_id}",
                headers=forwarded,
                timeout=get_settings().customers_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise CustomersUnavailable from exc

        if response.status_code == 404:
            raise CustomerNotFound
        if response.status_code == 403:
            raise CustomerForbidden
        if response.status_code != 200:
            raise CustomersUnavailable(f"customers відповів {response.status_code}")

        body = response.json()
        return CustomerSnapshot(id=uuid.UUID(body["id"]), name=body["name"], phone=body["phone"])
