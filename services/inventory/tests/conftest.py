import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

# Тести ганяються на SQLite у пам'яті — жодних зовнішніх залежностей.
# Має бути раніше за імпорт app.*, бо налаштування кешуються.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["RABBITMQ_URL"] = ""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.catalog_client import CatalogClient
from app.db import Base, get_session
from app.handlers import HANDLERS
from app.main import app

FILTER = "9a000000-0000-0000-0000-000000000001"
OIL = "9a000000-0000-0000-0000-000000000002"

CATALOG = {
    FILTER: {
        "id": FILTER,
        "sku": "OC90",
        "brand": "MAHLE",
        "name": "Фільтр оливний",
        "unit": "pcs",
    },
    OIL: {"id": OIL, "sku": "5W30-1L", "brand": "CASTROL", "name": "Олива 5W-30", "unit": "l"},
}


def catalog_handler(request: httpx.Request) -> httpx.Response:
    if "catalog.read" not in request.headers.get("x-user-permissions", ""):
        return httpx.Response(403, json={"detail": "Бракує права catalog.read"})
    part = CATALOG.get(request.url.path.rsplit("/", 1)[-1])
    return httpx.Response(200, json=part) if part else httpx.Response(404, json={"detail": "—"})


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


def as_user(permissions: str) -> dict[str, str]:
    return {
        "X-User-Id": "00000000-0000-0000-0000-0000000000aa",
        "X-User-Role": "storekeeper",
        "X-User-Permissions": permissions,
    }


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    http = httpx.AsyncClient(transport=httpx.MockTransport(catalog_handler))
    app.state.catalog = CatalogClient(http, "http://catalog")
    app.dependency_overrides[get_session] = lambda: session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=as_user("inventory.read,inventory.write,catalog.read"),
    ) as c:
        yield c
    app.dependency_overrides.clear()
    await http.aclose()


Deliver = Callable[..., Awaitable[list[tuple[str, dict[str, Any]]]]]


class Clock:
    """Час подій: кожна наступна — на секунду пізніше, якщо не вказано інше."""

    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def tick(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def deliver(session: AsyncSession, clock: Clock) -> Deliver:
    """Доставити подію обробнику так, як це робить consumer: обробка → коміт."""

    async def run(
        name: str, payload: dict[str, Any], at: datetime | None = None
    ) -> list[tuple[str, dict[str, Any]]]:
        moment = at or clock.tick()
        event = {"event": name, "occurred_at": moment.isoformat(), "payload": payload}
        out = await HANDLERS[name](session, event, moment)
        await session.commit()
        return out

    return run


def reserved(line: str, order: str, part: str, qty: str) -> dict[str, str]:
    return {
        "order_id": order,
        "order_number": "2026-00001",
        "line_id": line,
        "part_id": part,
        "code": "MAHLE OC90" if part == FILTER else "CASTROL 5W30-1L",
        "name": "Фільтр оливний" if part == FILTER else "Олива 5W-30",
        "unit": "pcs" if part == FILTER else "l",
        "qty": qty,
    }


def new_id() -> str:
    return str(uuid.uuid4())
