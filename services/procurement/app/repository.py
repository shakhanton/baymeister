"""Запити до бази. Роути й обробники подій SQL не пишуть — лише кличуть сюди."""

import math
import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Counter, Line, Need, Order, Supplier

# Замовлення, в яких деталь «уже їде»: чернетка або відправлене й недоотримане.
ACTIVE = ("draft", "ordered")


async def next_number(session: AsyncSession, now: datetime) -> str:
    """Наступний номер у році: «PO-2026-00042». Один UPDATE … RETURNING під блокуванням."""
    year = now.astimezone(ZoneInfo(get_settings().business_timezone)).year
    assert session.bind is not None
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    await session.execute(
        insert(Counter).values(year=year, last=0).on_conflict_do_nothing(index_elements=["year"])
    )
    last = await session.scalar(
        update(Counter)
        .where(Counter.year == year)
        .values(last=Counter.last + 1)
        .returning(Counter.last)
    )
    return f"PO-{year}-{int(last or 0):05d}"


# ── Постачальники ──────────────────────────────────────────────────────────


async def suppliers(
    session: AsyncSession, *, search: str | None, archived: bool, limit: int, offset: int
) -> tuple[list[Supplier], int]:
    query = select(Supplier)
    if not archived:
        query = query.where(Supplier.active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        query = query.where(
            or_(
                Supplier.name.ilike(like),
                Supplier.edrpou.ilike(like),
                Supplier.phone.ilike(like),
                Supplier.contact.ilike(like),
            )
        )
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(query.order_by(Supplier.name_key).limit(limit).offset(offset))
    return list(rows.all()), int(total or 0)


async def supplier_name_taken(
    session: AsyncSession, name: str, *, except_id: uuid.UUID | None = None
) -> bool:
    query = select(Supplier.id).where(Supplier.name_key == name.casefold())
    if except_id is not None:
        query = query.where(Supplier.id != except_id)
    return (await session.scalar(query)) is not None


# ── Замовлення ─────────────────────────────────────────────────────────────


async def orders(
    session: AsyncSession,
    *,
    search: str | None,
    status: str | None,
    supplier_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Order], int]:
    query = select(Order).join(Order.supplier)
    if status:
        query = query.where(Order.status == status)
    if supplier_id:
        query = query.where(Order.supplier_id == supplier_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(or_(Order.number.ilike(like), Supplier.name.ilike(like)))
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(
        query.order_by(Order.created_at.desc()).limit(limit).offset(offset)
    )
    return list(rows.unique().all()), int(total or 0)


async def lock_order(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    """Замовлення під блокуванням: два одночасні приходи не порахують ту саму нестачу."""
    result = await session.execute(
        select(Order).where(Order.id == order_id).with_for_update(of=Order)
    )
    return result.unique().scalar_one_or_none()


async def active_order(session: AsyncSession, part_id: uuid.UUID) -> Order | None:
    """Чернетка чи відправлене замовлення, де цю деталь ще не отримали повністю."""
    result = await session.execute(
        select(Order)
        .join(Order.lines)
        .where(
            Line.part_id == part_id,
            Order.status.in_(ACTIVE),
            Line.qty_received < Line.qty,
        )
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    return result.unique().scalar_one_or_none()


async def last_line(session: AsyncSession, part_id: uuid.UUID) -> tuple[Line, Supplier] | None:
    """Останній раз цю деталь замовляли — у кого (з діючих постачальників) і за скільки."""
    result = await session.execute(
        select(Line, Supplier)
        .join(Line.order)
        .join(Order.supplier)
        .where(Line.part_id == part_id, Order.status != "cancelled", Supplier.active.is_(True))
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    row = result.first()
    return (row[0], row[1]) if row is not None else None


async def draft_for(
    session: AsyncSession, supplier: Supplier, now: datetime, *, auto: bool
) -> Order:
    """Чернетка для постачальника: наявна або нова. Одна чернетка — один лист постачальнику."""
    existing = await session.scalar(
        select(Order)
        .where(Order.supplier_id == supplier.id, Order.status == "draft")
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        return existing
    order = Order(
        number=await next_number(session, now),
        supplier_id=supplier.id,
        supplier=supplier,
        status="draft",
        auto=auto,
        note="Сформовано автоматично: деталей на складі менше за мінімум" if auto else None,
        created_at=now,
        lines=[],
        receipts=[],
    )
    session.add(order)
    await session.flush()
    return order


def suggested_qty(need: Need) -> Decimal:
    """Скільки замовити: довести вільний залишок до двох мінімумів. Штуки — цілі."""
    qty = max(need.min_qty * 2 - need.free, need.min_qty, Decimal("0.001"))
    if need.unit == "pcs":
        qty = Decimal(math.ceil(qty))
    return qty.quantize(Decimal("0.001"))


async def add_need_to_draft(
    session: AsyncSession,
    need: Need,
    supplier: Supplier,
    now: datetime,
    *,
    auto: bool,
    unit_cost: Decimal | None = None,
) -> Order:
    order = await draft_for(session, supplier, now, auto=auto)
    existing = next((line for line in order.lines if line.part_id == need.part_id), None)
    if existing is None:
        if unit_cost is None:
            previous = await last_line(session, need.part_id)
            unit_cost = previous[0].unit_cost if previous is not None else Decimal(0)
        order.lines.append(
            Line(
                part_id=need.part_id,
                sku=need.sku,
                brand=need.brand,
                name=need.name,
                unit=need.unit,
                qty=suggested_qty(need),
                unit_cost=unit_cost,
                qty_received=Decimal(0),
                created_at=now,
            )
        )
        await session.flush()
    return order


# ── Потреби ────────────────────────────────────────────────────────────────


async def open_needs(session: AsyncSession) -> list[Need]:
    rows = await session.scalars(
        select(Need).where(Need.open.is_(True)).order_by(Need.raised_at.desc())
    )
    return list(rows.all())
