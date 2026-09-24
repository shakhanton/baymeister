import os
from collections.abc import AsyncIterator

# Тести ганяються на SQLite у пам'яті — жодних зовнішніх залежностей.
# Має бути раніше за імпорт app.*, бо налаштування кешуються.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["RABBITMQ_URL"] = ""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app import repository
from app.db import Base, get_session
from app.main import app
from app.models import User
from app.schemas import UserCreate

OWNER_PASSWORD = "owner-password"


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
async def owner(session: AsyncSession) -> User:
    user = await repository.create(
        session,
        UserCreate(
            email="owner@example.com",
            name="Власник",
            role="owner",
            password=OWNER_PASSWORD,
        ),
    )
    await session.commit()
    return user


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Клієнт без заголовків X-User-* — як запит, що не пройшов gateway."""
    app.dependency_overrides[get_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def as_user(user: User, permissions: str) -> dict[str, str]:
    """Заголовки, які gateway виставляє після перевірки токена."""
    return {
        "X-User-Id": str(user.id),
        "X-User-Role": user.role,
        "X-User-Permissions": permissions,
    }


@pytest.fixture
def as_owner(owner: User) -> dict[str, str]:
    return as_user(owner, "*")
