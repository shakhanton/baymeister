"""
Уся арифметика складу в одному місці: прихід, FIFO-списання, рівні.

Кожна операція, що змінює залишок деталі, спершу блокує її картку
(SELECT … FOR UPDATE). Два одночасні списання з тієї самої партії інакше
обидва побачили б однаковий залишок.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item, Lot, Movement, Reservation
from app.money import quantize

ZERO = Decimal(0)


@dataclass(frozen=True)
class Levels:
    on_hand: Decimal
    reserved: Decimal
    value: Decimal

    @property
    def free(self) -> Decimal:
        return self.on_hand - self.reserved


def is_low(item: Item, levels: Levels) -> bool:
    """Мінімум 0 — «не стежити». Інакше низько, коли вільного менше за мінімум."""
    return item.min_qty > 0 and levels.free < item.min_qty


async def lock(session: AsyncSession, part_id: uuid.UUID) -> Item | None:
    result = await session.execute(select(Item).where(Item.part_id == part_id).with_for_update())
    return result.scalar_one_or_none()


async def levels(session: AsyncSession, part_id: uuid.UUID) -> Levels:
    on_hand, value = (
        await session.execute(
            select(
                func.coalesce(func.sum(Lot.qty_left), 0),
                func.coalesce(func.sum(Lot.qty_left * Lot.unit_cost), 0),
            ).where(Lot.part_id == part_id)
        )
    ).one()
    reserved = await session.scalar(
        select(func.coalesce(func.sum(Reservation.qty), 0)).where(
            Reservation.part_id == part_id, Reservation.active.is_(True)
        )
    )
    return Levels(
        on_hand=Decimal(on_hand), reserved=Decimal(reserved or 0), value=quantize(Decimal(value))
    )


async def receive(
    session: AsyncSession,
    item: Item,
    *,
    qty: Decimal,
    unit_cost: Decimal,
    source: str,
    note: str | None,
    now: datetime,
) -> Lot:
    lot = Lot(
        part_id=item.part_id,
        received_at=now,
        qty_received=qty,
        qty_left=qty,
        unit_cost=unit_cost,
        source=source,
        note=note,
    )
    session.add(lot)
    session.add(
        Movement(
            part_id=item.part_id,
            kind="receipt" if source == "receipt" else "count_plus",
            qty=qty,
            cost=quantize(qty * unit_cost),
            note=note,
            created_at=now,
        )
    )
    await session.flush()
    return lot


@dataclass(frozen=True)
class WriteOff:
    issued: Decimal
    cost: Decimal
    short: Decimal


async def write_off(
    session: AsyncSession,
    item: Item,
    *,
    qty: Decimal,
    kind: str,
    now: datetime,
    note: str | None = None,
    order_id: uuid.UUID | None = None,
    order_number: str | None = None,
    line_id: uuid.UUID | None = None,
) -> WriteOff:
    """
    Списати з найстаріших партій. Якщо партій не вистачає — списується те,
    що є, а решта повертається як `short`: від'ємного залишку склад не має.
    """
    lots = (
        await session.execute(
            select(Lot)
            .where(Lot.part_id == item.part_id, Lot.qty_left > 0)
            .order_by(Lot.received_at, Lot.id)
        )
    ).scalars()

    left = qty
    cost = ZERO
    for lot in lots:
        if left <= 0:
            break
        take = min(lot.qty_left, left)
        lot.qty_left -= take
        cost += take * lot.unit_cost
        left -= take

    issued = qty - left
    if left > 0 and kind == "issue":
        note = f"Не вистачило {left:.3f} — перевірте залишок"
    if issued > 0 or kind == "issue":
        session.add(
            Movement(
                part_id=item.part_id,
                kind=kind,
                qty=-issued,
                cost=quantize(cost),
                order_id=order_id,
                order_number=order_number,
                line_id=line_id,
                note=note,
                created_at=now,
            )
        )
    await session.flush()
    return WriteOff(issued=issued, cost=quantize(cost), short=left)


async def last_cost(session: AsyncSession, part_id: uuid.UUID) -> Decimal:
    """Ціна останнього приходу — для надлишку, знайденого на інвентаризації."""
    cost = await session.scalar(
        select(Lot.unit_cost)
        .where(Lot.part_id == part_id)
        .order_by(Lot.received_at.desc())
        .limit(1)
    )
    return Decimal(cost) if cost is not None else ZERO
