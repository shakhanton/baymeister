import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import LaborRate, Part, Service
from app.schemas import PartCreate, PartUpdate, ServiceCreate, ServiceUpdate

# ── Ставка ──────────────────────────────────────────────────────────────────


async def rate_at(session: AsyncSession, at: datetime | None = None) -> LaborRate | None:
    """Ставка, що діяла в момент `at`: остання з effective_from <= at."""
    moment = at or datetime.now(UTC)
    result = await session.execute(
        select(LaborRate)
        .where(LaborRate.effective_from <= moment)
        .order_by(LaborRate.effective_from.desc(), LaborRate.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def add_rate(
    session: AsyncSession, amount: Decimal, effective_from: datetime | None
) -> LaborRate:
    rate = LaborRate(amount=amount, effective_from=effective_from or datetime.now(UTC))
    session.add(rate)
    await session.flush()
    await session.refresh(rate)
    return rate


async def list_rates(session: AsyncSession) -> list[LaborRate]:
    result = await session.execute(
        select(LaborRate).order_by(LaborRate.effective_from.desc(), LaborRate.created_at.desc())
    )
    return list(result.scalars().all())


# ── Роботи ──────────────────────────────────────────────────────────────────


async def get_service(session: AsyncSession, service_id: uuid.UUID) -> Service | None:
    return await session.get(Service, service_id)


async def find_active_service(session: AsyncSession, code: str) -> Service | None:
    result = await session.execute(
        select(Service).where(Service.code == code, Service.archived_at.is_(None)).limit(1)
    )
    return result.scalar_one_or_none()


async def list_services(
    session: AsyncSession,
    *,
    search: str | None,
    category: str | None,
    archived: bool,
    limit: int,
    offset: int,
) -> tuple[list[Service], int]:
    conditions: list[ColumnElement[bool]] = [
        Service.archived_at.is_not(None) if archived else Service.archived_at.is_(None)
    ]
    if category:
        conditions.append(Service.category == category)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Service.code.ilike(pattern),
                Service.name.ilike(pattern),
                Service.category.ilike(pattern),
            )
        )

    total = await session.scalar(select(func.count()).select_from(Service).where(*conditions))
    result = await session.execute(
        select(Service)
        .where(*conditions)
        .order_by(Service.category, Service.name)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)


async def create_service(session: AsyncSession, data: ServiceCreate) -> Service:
    service = Service(**data.model_dump())
    session.add(service)
    await session.flush()
    await session.refresh(service)
    return service


async def update_service(session: AsyncSession, service: Service, data: ServiceUpdate) -> Service:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    await session.flush()
    await session.refresh(service)
    return service


# ── Запчастини ──────────────────────────────────────────────────────────────


async def get_part(session: AsyncSession, part_id: uuid.UUID) -> Part | None:
    return await session.get(Part, part_id)


async def find_active_part(session: AsyncSession, sku: str, brand: str) -> Part | None:
    result = await session.execute(
        select(Part)
        .where(
            Part.sku == sku,
            Part.brand == brand,
            Part.archived_at.is_(None),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_parts(
    session: AsyncSession, *, search: str | None, archived: bool, limit: int, offset: int
) -> tuple[list[Part], int]:
    conditions: list[ColumnElement[bool]] = [
        Part.archived_at.is_not(None) if archived else Part.archived_at.is_(None)
    ]
    if search:
        pattern = f"%{search.strip()}%"
        # Артикул шукається і без пробілів: «oc 90» знайде OC90.
        compact = f"%{''.join(search.split()).upper()}%"
        conditions.append(
            or_(
                Part.sku.ilike(compact),
                Part.name.ilike(pattern),
                Part.brand.ilike(pattern),
            )
        )

    total = await session.scalar(select(func.count()).select_from(Part).where(*conditions))
    result = await session.execute(
        select(Part).where(*conditions).order_by(Part.name, Part.brand).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)


async def create_part(session: AsyncSession, data: PartCreate) -> Part:
    part = Part(**data.model_dump())
    session.add(part)
    await session.flush()
    await session.refresh(part)
    return part


async def update_part(session: AsyncSession, part: Part, data: PartUpdate) -> Part:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(part, field, value)
    await session.flush()
    await session.refresh(part)
    return part


async def archive(session: AsyncSession, item: Service | Part) -> None:
    item.archived_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(item)
