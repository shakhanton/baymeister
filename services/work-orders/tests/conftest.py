import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

# Тести ганяються на SQLite у пам'яті — жодних зовнішніх залежностей.
# Має бути раніше за імпорт app.*, бо налаштування кешуються.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["RABBITMQ_URL"] = ""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_session
from app.main import app
from app.peers import Peers

PETRENKO = "11111111-1111-1111-1111-111111111111"  # знижка 5 %
KOVAL = "22222222-2222-2222-2222-222222222222"  # без знижки
GOLF = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"  # авто Петренка

OIL_CHANGE = "5e000000-0000-0000-0000-000000000001"  # 1.35 год × 850 = 1147.50
DIAG = "5e000000-0000-0000-0000-000000000002"  # ставку не задано — ціни немає
OLD_SERVICE = "5e000000-0000-0000-0000-000000000003"  # в архіві
FILTER = "9a000000-0000-0000-0000-000000000001"  # 245.50 за шт.
OIL_5W30 = "9a000000-0000-0000-0000-000000000002"  # 320.00 за л


@dataclass
class FakePeers:
    customers: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            PETRENKO: {
                "id": PETRENKO,
                "name": "Петренко Іван",
                "phone": "+380671234567",
                "discount_percent": 5,
            },
            KOVAL: {
                "id": KOVAL,
                "name": "Коваль Олена",
                "phone": "+380509876543",
                "discount_percent": 0,
            },
        }
    )
    vehicles: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            GOLF: {
                "id": GOLF,
                "customer_id": PETRENKO,
                "plate": "AA1234BC",
                "make": "Volkswagen",
                "model": "Golf",
            },
        }
    )
    services: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            OIL_CHANGE: {
                "id": OIL_CHANGE,
                "code": "ENG-OIL",
                "name": "Заміна оливи",
                "price": "1147.50",
                "archived_at": None,
            },
            DIAG: {
                "id": DIAG,
                "code": "DIAG",
                "name": "Діагностика",
                "price": None,
                "archived_at": None,
            },
            OLD_SERVICE: {
                "id": OLD_SERVICE,
                "code": "OLD",
                "name": "Стара робота",
                "price": "100.00",
                "archived_at": "2026-01-01T00:00:00Z",
            },
        }
    )
    parts: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            FILTER: {
                "id": FILTER,
                "sku": "OC90",
                "brand": "MAHLE",
                "name": "Фільтр оливний",
                "unit": "pcs",
                "price": "245.50",
                "archived_at": None,
            },
            OIL_5W30: {
                "id": OIL_5W30,
                "sku": "5W30-1L",
                "brand": "CASTROL",
                "name": "Олива 5W-30",
                "unit": "l",
                "price": "320.00",
                "archived_at": None,
            },
        }
    )
    down: set[str] = field(default_factory=set)

    def handler(self, request: httpx.Request) -> httpx.Response:
        block = request.url.host
        if block in self.down:
            raise httpx.ConnectError("connection refused", request=request)
        if f"{block}.read" not in request.headers.get("x-user-permissions", ""):
            return httpx.Response(403, json={"detail": f"Бракує права {block}.read"})
        path = request.url.path
        key = path.rsplit("/", 1)[-1]
        store = {
            "customers": self.customers,
            "vehicles": self.vehicles,
        }.get(block) or (self.services if "/services/" in path else self.parts)
        item = store.get(key)
        if item is None:
            return httpx.Response(404, json={"detail": "Не знайдено"})
        return httpx.Response(200, json=item)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s

    await engine.dispose()


@pytest.fixture
def peers() -> FakePeers:
    return FakePeers()


def as_user(permissions: str) -> dict[str, str]:
    """Заголовки, які gateway виставляє після перевірки токена."""
    return {
        "X-User-Id": "00000000-0000-0000-0000-0000000000aa",
        "X-User-Role": "manager",
        "X-User-Permissions": permissions,
    }


MANAGER = "work_orders.read,work_orders.write,customers.read,vehicles.read,catalog.read"


@pytest.fixture
async def client(session: AsyncSession, peers: FakePeers) -> AsyncIterator[AsyncClient]:
    http = httpx.AsyncClient(transport=httpx.MockTransport(peers.handler))
    # ASGITransport не запускає lifespan — стан, який він створює, ставимо тут.
    app.state.peers = Peers(http, "http://customers", "http://vehicles", "http://catalog")
    app.dependency_overrides[get_session] = lambda: session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=as_user(MANAGER)
    ) as c:
        yield c

    app.dependency_overrides.clear()
    await http.aclose()


@pytest.fixture
async def order(client: AsyncClient) -> dict[str, Any]:
    response = await client.post(
        "/work-orders",
        json={
            "customer_id": PETRENKO,
            "vehicle_id": GOLF,
            "complaint": "Стукає спереду",
            "mileage_km": 187000,
        },
    )
    body: dict[str, Any] = response.json()
    return body
