import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import Customer
from app.schemas import CustomerCreate, CustomerUpdate


async def get(session: AsyncSession, customer_id: uuid.UUID) -> Customer | None:
    return await session.get(Customer, customer_id)


async def get_by_phone(session: AsyncSession, phone: str) -> Customer | None:
    result = await session.execute(select(Customer).where(Customer.phone == phone))
    return result.scalar_one_or_none()


async def list_page(
    session: AsyncSession,
    *,
    search: str | None,
    type_: str | None,
    archived: bool,
    limit: int,
    offset: int,
) -> tuple[list[Customer], int]:
    conditions: list[ColumnElement[bool]] = []

    conditions.append(
        Customer.archived_at.is_not(None) if archived else Customer.archived_at.is_(None)
    )

    if type_ is not None:
        conditions.append(Customer.type == type_)

    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Customer.name.ilike(pattern),
                Customer.phone.ilike(pattern),
                Customer.tax_id.ilike(pattern),
            )
        )

    total = await session.scalar(select(func.count()).select_from(Customer).where(*conditions))

    result = await session.execute(
        select(Customer)
        .where(*conditions)
        .order_by(Customer.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(result.scalars().all()), int(total or 0)


async def create(session: AsyncSession, data: CustomerCreate) -> Customer:
    customer = Customer(**data.model_dump())
    session.add(customer)
    await session.flush()
    await session.refresh(customer)
    return customer


async def update(session: AsyncSession, customer: Customer, data: CustomerUpdate) -> Customer:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await session.flush()
    await session.refresh(customer)
    return customer


async def archive(session: AsyncSession, customer: Customer) -> Customer:
    customer.archived_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(customer)
    return customer
