import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

# Тести ганяються на SQLite у пам'яті — жодних зовнішніх залежностей.
# Має бути раніше за імпорт app.*, бо налаштування кешуються.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["RABBITMQ_URL"] = ""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.customers_client import CustomersClient
from app.db import Base, get_session
from app.main import app

PETRENKO_ID = "11111111-1111-1111-1111-111111111111"
KOVAL_ID = "22222222-2222-2222-2222-222222222222"


@dataclass
class FakeCustomers:
    """Підмінений сервіс customers: два клієнти, решта — 404."""

    customers: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            PETRENKO_ID: {"id": PETRENKO_ID, "name": "Петренко Іван", "phone": "+380671234567"},
            KOVAL_ID: {"id": KOVAL_ID, "name": "Коваль Олена", "phone": "+380509876543"},
        }
    )
    down: bool = False
    requests: list[httpx.Request] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        self.requests.append(request)
        if "customers.read" not in request.headers.get("x-user-permissions", ""):
            return httpx.Response(403, json={"detail": "Бракує права customers.read"})
        customer = self.customers.get(request.url.path.rsplit("/", 1)[-1])
        if customer is None:
            return httpx.Response(404, json={"detail": "Клієнта не знайдено"})
        return httpx.Response(200, json=customer)


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
def customers() -> FakeCustomers:
    return FakeCustomers()


def as_user(permissions: str) -> dict[str, str]:
    """Заголовки, які gateway виставляє після перевірки токена."""
    return {
        "X-User-Id": "00000000-0000-0000-0000-0000000000aa",
        "X-User-Role": "manager",
        "X-User-Permissions": permissions,
    }


@pytest.fixture
async def client(session: AsyncSession, customers: FakeCustomers) -> AsyncIterator[AsyncClient]:
    """Клієнт від імені адміністратора: права на автомобілі й читання клієнтів."""
    http = httpx.AsyncClient(transport=httpx.MockTransport(customers.handler))
    # ASGITransport не запускає lifespan — стан, який він створює, ставимо тут.
    app.state.customers = CustomersClient(http, "http://customers")
    app.dependency_overrides[get_session] = lambda: session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=as_user("vehicles.read,vehicles.write,customers.read"),
    ) as c:
        yield c

    app.dependency_overrides.clear()
    await http.aclose()
