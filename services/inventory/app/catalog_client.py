"""
Читання деталі з catalog — лише при приході, від імені того самого користувача.
Далі картка оновлюється подіями part.created / part.updated.
"""

import uuid
from dataclasses import dataclass

import httpx

from app.config import get_settings

FORWARDED_HEADERS = ("x-user-id", "x-user-role", "x-user-permissions", "x-request-id")


class PartNotFound(Exception):
    pass


class CatalogForbidden(Exception):
    pass


class CatalogUnavailable(Exception):
    pass


@dataclass(frozen=True)
class PartSnapshot:
    id: uuid.UUID
    sku: str
    brand: str
    name: str
    unit: str


class CatalogClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def part(self, part_id: uuid.UUID, headers: dict[str, str]) -> PartSnapshot:
        forwarded = {k: v for k, v in headers.items() if k.lower() in FORWARDED_HEADERS}
        try:
            response = await self._http.get(
                f"{self._base_url}/catalog/parts/{part_id}",
                headers=forwarded,
                timeout=get_settings().peers_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise CatalogUnavailable from exc
        if response.status_code == 404:
            raise PartNotFound
        if response.status_code == 403:
            raise CatalogForbidden
        if response.status_code != 200:
            raise CatalogUnavailable
        body = response.json()
        return PartSnapshot(
            id=uuid.UUID(body["id"]),
            sku=body["sku"],
            brand=body["brand"],
            name=body["name"],
            unit=body["unit"],
        )
