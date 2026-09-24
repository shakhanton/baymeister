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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_session
from app.main import app
from app.peers import Peers

PETRENKO = "11111111-1111-1111-1111-111111111111"
KOVAL = "22222222-2222-2222-2222-222222222222"
GOLF = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"  # належить Петренку


@dataclass
class FakePeers:
    """Підмінені customers і vehicles."""

    customers: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            PETRENKO: {"id": PETRENKO, "name": "Петренко Іван", "phone": "+380671234567"},
            KOVAL: {"id": KOVAL, "name": "Коваль Олена", "phone": "+380509876543"},
        }
    )
    vehicles: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            GOLF: {
                "id": GOLF,
                "customer_id": PETRENKO,
                "plate": "AA1234BC",
                "make": "Volkswagen",
                "model": "Golf",
            }
        }
    )
    down: set[str] = field(default_factory=set)
    requests: list[httpx.Request] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        block = request.url.host
        if block in self.down:
            raise httpx.ConnectError("connection refused", request=request)
        self.requests.append(request)
        if f"{block}.read" not in request.headers.get("x-user-permissions", ""):
            return httpx.Response(403, json={"detail": f"Бракує права {block}.read"})
        store = self.customers if block == "customers" else self.vehicles
        item = store.get(request.url.path.rsplit("/", 1)[-1])
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


MANAGER = "scheduling.read,scheduling.write,customers.read,vehicles.read"


@pytest.fixture
async def client(session: AsyncSession, peers: FakePeers) -> AsyncIterator[AsyncClient]:
    """Клієнт від імені адміністратора: запис і читання клієнтів та авто."""
    http = httpx.AsyncClient(transport=httpx.MockTransport(peers.handler))
    # ASGITransport не запускає lifespan — стан, який він створює, ставимо тут.
    app.state.peers = Peers(http, "http://customers", "http://vehicles")
    app.dependency_overrides[get_session] = lambda: session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=as_user(MANAGER)
    ) as c:
        yield c

    app.dependency_overrides.clear()
    await http.aclose()


@pytest.fixture
async def lift(client: AsyncClient) -> str:
    response = await client.post("/scheduling/bays", json={"name": "Підйомник 1", "kind": "lift"})
    bay_id: str = response.json()["id"]
    return bay_id
