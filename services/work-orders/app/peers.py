"""
Синхронне читання з сусідніх блоків.

- При відкритті наряду: клієнт (імʼя, телефон, знижка) і авто (чиє воно, держномер).
- При додаванні рядка: позиція з каталогу з поточною ціною.

Далі копії клієнта й авто оновлюються подіями; ціни в наряді не оновлюються
ніколи — вони зафіксовані свідомо.

Запити йдуть від імені того самого користувача: заголовки X-User-* передаються
далі, і сусідній блок сам вирішує, чи можна цьому користувачу це бачити.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from app.config import get_settings

FORWARDED_HEADERS = ("x-user-id", "x-user-role", "x-user-permissions", "x-request-id")

BLOCK_TITLE = {"customers": "Клієнти", "vehicles": "Автомобілі", "catalog": "Послуги та прайс"}


class PeerNotFound(Exception):
    def __init__(self, block: str) -> None:
        super().__init__(block)
        self.block = block


class PeerForbidden(PeerNotFound):
    pass


class PeerUnavailable(PeerNotFound):
    pass


@dataclass(frozen=True)
class CustomerSnapshot:
    id: uuid.UUID
    name: str
    phone: str
    discount_percent: Decimal


@dataclass(frozen=True)
class VehicleSnapshot:
    id: uuid.UUID
    customer_id: uuid.UUID
    label: str


@dataclass(frozen=True)
class CatalogItem:
    id: uuid.UUID
    code: str
    name: str
    unit: str
    price: Decimal | None
    archived: bool


def vehicle_label(plate: str, make: str, model: str) -> str:
    return f"{plate} · {make} {model}"


class Peers:
    def __init__(
        self, http: httpx.AsyncClient, customers_url: str, vehicles_url: str, catalog_url: str
    ) -> None:
        self._http = http
        self._urls = {
            "customers": customers_url.rstrip("/"),
            "vehicles": vehicles_url.rstrip("/"),
            "catalog": catalog_url.rstrip("/"),
        }

    async def _get(self, block: str, path: str, headers: dict[str, str]) -> dict[str, Any]:
        forwarded = {k: v for k, v in headers.items() if k.lower() in FORWARDED_HEADERS}
        try:
            response = await self._http.get(
                self._urls[block] + path,
                headers=forwarded,
                timeout=get_settings().peers_timeout_seconds,
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
        body = await self._get("customers", f"/customers/{customer_id}", headers)
        return CustomerSnapshot(
            id=uuid.UUID(body["id"]),
            name=body["name"],
            phone=body["phone"],
            # customers віддає знижку числом — через str, щоб не тягнути float у Decimal.
            discount_percent=Decimal(str(body.get("discount_percent") or 0)),
        )

    async def vehicle(self, vehicle_id: uuid.UUID, headers: dict[str, str]) -> VehicleSnapshot:
        body = await self._get("vehicles", f"/vehicles/{vehicle_id}", headers)
        return VehicleSnapshot(
            id=uuid.UUID(body["id"]),
            customer_id=uuid.UUID(body["customer_id"]),
            label=vehicle_label(body["plate"], body["make"], body["model"]),
        )

    async def service(self, service_id: uuid.UUID, headers: dict[str, str]) -> CatalogItem:
        body = await self._get("catalog", f"/catalog/services/{service_id}", headers)
        return CatalogItem(
            id=uuid.UUID(body["id"]),
            code=body["code"],
            name=body["name"],
            unit="h",
            price=Decimal(body["price"]) if body["price"] is not None else None,
            archived=body.get("archived_at") is not None,
        )

    async def part(self, part_id: uuid.UUID, headers: dict[str, str]) -> CatalogItem:
        body = await self._get("catalog", f"/catalog/parts/{part_id}", headers)
        return CatalogItem(
            id=uuid.UUID(body["id"]),
            code=f"{body['brand']} {body['sku']}",
            name=body["name"],
            unit=body["unit"],
            price=Decimal(body["price"]),
            archived=body.get("archived_at") is not None,
        )
