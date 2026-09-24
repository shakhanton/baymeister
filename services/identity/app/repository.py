import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import User
from app.schemas import UserCreate, UserUpdate
from app.security import hash_password


async def get(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(User)) or 0)


async def count_active_owners(session: AsyncSession) -> int:
    total = await session.scalar(
        select(func.count()).select_from(User).where(User.role == "owner", User.is_active.is_(True))
    )
    return int(total or 0)


async def list_page(
    session: AsyncSession,
    *,
    search: str | None,
    inactive: bool,
    limit: int,
    offset: int,
) -> tuple[list[User], int]:
    conditions: list[ColumnElement[bool]] = [User.is_active.is_(not inactive)]

    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(User.name.ilike(pattern), User.email.ilike(pattern)))

    total = await session.scalar(select(func.count()).select_from(User).where(*conditions))

    result = await session.execute(
        select(User).where(*conditions).order_by(User.name).limit(limit).offset(offset)
    )

    return list(result.scalars().all()), int(total or 0)


async def create(session: AsyncSession, data: UserCreate) -> User:
    user = User(
        email=data.email,
        name=data.name,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def update(session: AsyncSession, user: User, data: UserUpdate) -> User:
    fields = data.model_dump(exclude_unset=True)
    password = fields.pop("password", None)
    for field, value in fields.items():
        setattr(user, field, value)
    if password is not None:
        user.password_hash = hash_password(password)
    await session.flush()
    await session.refresh(user)
    return user


async def set_active(session: AsyncSession, user: User, active: bool) -> User:
    user.is_active = active
    await session.flush()
    await session.refresh(user)
    return user


async def touch_login(session: AsyncSession, user: User) -> None:
    user.last_login_at = datetime.now(UTC)
    await session.flush()
