import uuid
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.config import get_settings
from app.models import Counter, Line, Order
from app.peers import CatalogItem, CustomerSnapshot, VehicleSnapshot
from app.schemas import OrderCreate


async def next_number(session: AsyncSession, now: datetime) -> str:
    """
    Наступний номер наряду в році: «2026-00042».

    Рядок лічильника створюється, якщо його ще немає (ON CONFLICT DO NOTHING),
    і збільшується одним UPDATE … RETURNING — під блокуванням рядка до кінця
    транзакції. Два одночасні наряди отримають різні номери.
    """
    year = now.astimezone(ZoneInfo(get_settings().business_timezone)).year
    dialect = session.bind.dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    await session.execute(
        insert(Counter).values(year=year, last=0).on_conflict_do_nothing(index_elements=["year"])
    )
    last = await session.scalar(
        update(Counter)
        .where(Counter.year == year)
        .values(last=Counter.last + 1)
        .returning(Counter.last)
    )
    return f"{year}-{int(last or 0):05d}"


async def get(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    return await session.get(Order, order_id)


async def list_page(
    session: AsyncSession,
    *,
    search: str | None,
    status: str | None,
    customer_id: uuid.UUID | None,
    vehicle_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Order], int]:
    conditions: list[ColumnElement[bool]] = []
    if status:
        conditions.append(Order.status == status)
    if customer_id:
        conditions.append(Order.customer_id == customer_id)
    if vehicle_id:
        conditions.append(Order.vehicle_id == vehicle_id)
    if search:
        pattern = f"%{search.strip()}%"
        # Держномер у копії — латиницею без пробілів; шукаємо і так, і як ввели.
        compact = f"%{''.join(search.split()).upper()}%"
        conditions.append(
            or_(
                Order.number.ilike(pattern),
                Order.vehicle_label.ilike(pattern),
                Order.vehicle_label.ilike(compact),
                Order.customer_name.ilike(pattern),
                Order.customer_phone.ilike(pattern),
            )
        )

    total = await session.scalar(select(func.count()).select_from(Order).where(*conditions))
    result = await session.execute(
        select(Order)
        .where(*conditions)
        .order_by(Order.opened_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)


async def create(
    session: AsyncSession,
    data: OrderCreate,
    customer: CustomerSnapshot,
    vehicle: VehicleSnapshot,
) -> Order:
    now = datetime.now(UTC)
    order = Order(
        number=await next_number(session, now),
        status="open",
        customer_id=customer.id,
        customer_name=customer.name,
        customer_phone=customer.phone,
        customer_synced_at=now,
        vehicle_id=vehicle.id,
        vehicle_label=vehicle.label,
        vehicle_synced_at=now,
        discount_percent=customer.discount_percent,
        appointment_id=data.appointment_id,
        complaint=data.complaint,
        mileage_km=data.mileage_km,
        opened_at=now,
        lines=[],
    )
    session.add(order)
    await session.flush()
    return order


async def add_line(
    session: AsyncSession, order: Order, kind: str, item: CatalogItem, qty: Decimal
) -> Line:
    position = max((x.position for x in order.lines), default=0) + 1
    assert item.price is not None
    line = Line(
        order_id=order.id,
        position=position,
        kind=kind,
        catalog_id=item.id,
        code=item.code,
        name=item.name,
        unit=item.unit,
        qty=qty,
        unit_price=item.price,
    )
    order.lines.append(line)
    await session.flush()
    return line


async def reload(session: AsyncSession, order: Order) -> Order:
    """Свіжий стан разом із рядками — після змін, перед відповіддю."""
    await session.refresh(order, attribute_names=["lines", "updated_at"])
    return order


# ── Копії з інших блоків ────────────────────────────────────────────────────


async def apply_customer_update(
    session: AsyncSession, *, customer_id: uuid.UUID, name: str, phone: str, occurred_at: datetime
) -> int:
    """Ідемпотентно й стійко до перестановки: новіша подія перемагає."""
    result = await session.execute(
        update(Order)
        .where(Order.customer_id == customer_id, Order.customer_synced_at < occurred_at)
        .values(customer_name=name, customer_phone=phone, customer_synced_at=occurred_at)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def apply_vehicle_update(
    session: AsyncSession, *, vehicle_id: uuid.UUID, label: str, occurred_at: datetime
) -> int:
    result = await session.execute(
        update(Order)
        .where(Order.vehicle_id == vehicle_id, Order.vehicle_synced_at < occurred_at)
        .values(vehicle_label=label, vehicle_synced_at=occurred_at)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
