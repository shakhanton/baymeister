import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item, Lot, Movement, Reservation
from app.stock import Levels


def _levels_query() -> Select[tuple[Item, Decimal, Decimal, Decimal]]:
    """Картка разом із рівнями — одним запитом для списку, без N+1."""
    lots = (
        select(
            Lot.part_id,
            func.sum(Lot.qty_left).label("on_hand"),
            func.sum(Lot.qty_left * Lot.unit_cost).label("value"),
        )
        .group_by(Lot.part_id)
        .subquery()
    )
    res = (
        select(Reservation.part_id, func.sum(Reservation.qty).label("reserved"))
        .where(Reservation.active.is_(True))
        .group_by(Reservation.part_id)
        .subquery()
    )
    on_hand = func.coalesce(lots.c.on_hand, 0)
    reserved = func.coalesce(res.c.reserved, 0)
    value = func.coalesce(lots.c.value, 0)
    return (
        select(Item, on_hand.label("on_hand"), reserved.label("reserved"), value.label("value"))
        .outerjoin(lots, lots.c.part_id == Item.part_id)
        .outerjoin(res, res.c.part_id == Item.part_id)
    )


async def list_page(
    session: AsyncSession, *, search: str | None, low: bool, limit: int, offset: int
) -> tuple[list[tuple[Item, Levels]], int]:
    query = _levels_query()
    if search:
        pattern = f"%{search.strip()}%"
        compact = f"%{''.join(search.split()).upper()}%"
        query = query.where(
            or_(
                Item.sku.ilike(compact),
                Item.brand.ilike(pattern),
                Item.name.ilike(pattern),
                Item.location.ilike(pattern),
            )
        )
    if low:
        cols = query.selected_columns
        query = query.where(Item.min_qty > 0, cols.on_hand - cols.reserved < Item.min_qty)

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await session.execute(query.order_by(Item.name, Item.brand).limit(limit).offset(offset))
    ).all()
    items = [
        (item, Levels(on_hand=Decimal(oh), reserved=Decimal(rs), value=Decimal(v)))
        for item, oh, rs, v in rows
    ]
    return items, int(total or 0)


async def get(session: AsyncSession, part_id: uuid.UUID) -> Item | None:
    return await session.get(Item, part_id)


async def lots_left(session: AsyncSession, part_id: uuid.UUID) -> list[Lot]:
    result = await session.execute(
        select(Lot)
        .where(Lot.part_id == part_id, Lot.qty_left > 0)
        .order_by(Lot.received_at, Lot.id)
    )
    return list(result.scalars().all())


async def active_reservations(session: AsyncSession, part_id: uuid.UUID) -> list[Reservation]:
    result = await session.execute(
        select(Reservation)
        .where(Reservation.part_id == part_id, Reservation.active.is_(True))
        .order_by(Reservation.synced_at)
    )
    return list(result.scalars().all())


async def movements(session: AsyncSession, part_id: uuid.UUID, limit: int = 50) -> list[Movement]:
    result = await session.execute(
        select(Movement)
        .where(Movement.part_id == part_id)
        .order_by(Movement.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def upsert_item(
    session: AsyncSession,
    *,
    part_id: uuid.UUID,
    sku: str,
    brand: str,
    name: str,
    unit: str,
    synced_at: datetime,
) -> Item:
    """Завести картку або освіжити копію з catalog, якщо дані новіші."""
    item = await session.get(Item, part_id)
    if item is None:
        item = Item(
            part_id=part_id,
            sku=sku,
            brand=brand,
            name=name,
            unit=unit,
            catalog_synced_at=synced_at,
            min_qty=Decimal(0),
        )
        session.add(item)
    elif item.catalog_synced_at < synced_at:
        item.sku, item.brand, item.name, item.unit = sku, brand, name, unit
        item.catalog_synced_at = synced_at
    await session.flush()
    return item
