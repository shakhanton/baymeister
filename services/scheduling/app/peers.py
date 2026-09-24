"""
Синхронне читання з сусідніх блоків — тільки при створенні запису.

Записуючи клієнта, треба переконатися, що клієнт і автомобіль існують, що авто
належить саме цьому клієнту, і взяти імʼя, телефон і держномер для дошки. Далі
копії оновлюються подіями, без запитів.

Запити йдуть від імені того самого користувача: заголовки X-User-* передаються
далі, і сусідній блок сам вирішує, чи можна цьому користувачу це бачити.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings

FORWARDED_HEADERS = ("x-user-id", "x-user-role", "x-user-permissions", "x-request-id")


class PeerNotFound(Exception):
    pass


class PeerForbidden(Exception):
    pass


class PeerUnavailable(Exception):
    def __init__(self, block: str) -> None:
        super().__init__(block)
        self.block = block


@dataclass(frozen=True)
class CustomerSnapshot:
    id: uuid.UUID
    name: str
    phone: str


@dataclass(frozen=True)
class VehicleSnapshot:
    id: uuid.UUID
    customer_id: uuid.UUID
    label: str


def vehicle_label(plate: str, make: str, model: str) -> str:
    return f"{plate} · {make} {model}"


class Peers:
    def __init__(self, http: httpx.AsyncClient, customers_url: str, vehicles_url: str) -> None:
        self._http = http
        self._customers = customers_url.rstrip("/")
        self._vehicles = vehicles_url.rstrip("/")

    async def _get(self, block: str, url: str, headers: dict[str, str]) -> dict[str, Any]:
        forwarded = {k: v for k, v in headers.items() if k.lower() in FORWARDED_HEADERS}
        try:
            response = await self._http.get(
                url, headers=forwarded, timeout=get_settings().peers_timeout_seconds
            )
        except httpx.HTTPError as exc:
            raise PeerUnavailable(block) from exc

        if response.status_code == 404:
            raise PeerNotFound(block)
        if response.status_code == 403:
            raise PeerForbidden(block)
        if response.status_code != 200:
            raise PeerUnavailable(block)
        body: dict[str, Any] = response.json()
        return body

    async def customer(self, customer_id: uuid.UUID, headers: dict[str, str]) -> CustomerSnapshot:
        body = await self._get("customers", f"{self._customers}/customers/{customer_id}", headers)
        return CustomerSnapshot(id=uuid.UUID(body["id"]), name=body["name"], phone=body["phone"])

    async def vehicle(self, vehicle_id: uuid.UUID, headers: dict[str, str]) -> VehicleSnapshot:
        body = await self._get("vehicles", f"{self._vehicles}/vehicles/{vehicle_id}", headers)
        return VehicleSnapshot(
            id=uuid.UUID(body["id"]),
            customer_id=uuid.UUID(body["customer_id"]),
            label=vehicle_label(body["plate"], body["make"], body["model"]),
        )
