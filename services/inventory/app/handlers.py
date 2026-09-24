"""
Обробники подій — серце складу.

Резерви й списання приходять не запитами, а подіями від work-orders. Брокер
гарантує at-least-once і не гарантує порядок, тому кожен обробник:

- **ідемпотентний** — повтор тієї самої події нічого не змінює;
- **стійкий до перестановки** — старіша подія не перезаписує новішу
  (порівнюється час події з `synced_at`);
- **блокує картку деталі** перед зміною залишку.

Обробник повертає події, які треба опублікувати, — публікуються вони після
коміту, щоб не оголосити про те, що відкотилося.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import repository, stock
from app.models import Item, Movement, Reservation

Outgoing = list[tuple[str, dict[str, Any]]]


def _qty(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.001"))


def _split_code(code: str) -> tuple[str, str]:
    """work-orders кладе в код «БРЕНД АРТИКУЛ»."""
    brand, _, sku = code.partition(" ")
    return (brand, sku) if sku else ("", brand)


async def _low_signal(session: AsyncSession, item: Item, was_low: bool) -> Outgoing:
    """stock.low — лише на перетині порогу вниз, а не на кожну подію під ним."""
    now = await stock.levels(session, item.part_id)
    if stock.is_low(item, now) and not was_low:
        return [("stock.low", stock.low_payload(item, now))]
    return []


async def on_part_upsert(session: AsyncSession, event: dict[str, Any], at: datetime) -> Outgoing:
    p = event["payload"]
    await repository.upsert_item(
        session,
        part_id=uuid.UUID(p["id"]),
        sku=p["sku"],
        brand=p["brand"],
        name=p.get("name") or p["sku"],
        unit=p.get("unit") or "pcs",
        synced_at=at,
    )
    return []


async def on_parts_reserved(session: AsyncSession, event: dict[str, Any], at: datetime) -> Outgoing:
    p = event["payload"]
    part_id = uuid.UUID(p["part_id"])
    brand, sku = _split_code(p.get("code", ""))

    # Картку заводимо, якщо деталь ще не бачили; catalog_synced_at — з минулого,
    # щоб перша ж подія від catalog її освіжила.
    await repository.upsert_item(
        session,
        part_id=part_id,
        sku=sku or p["part_id"][:8],
        brand=brand,
        name=p.get("name") or sku,
        unit=p.get("unit") or "pcs",
        synced_at=datetime.min.replace(tzinfo=at.tzinfo),
    )
    item = await stock.lock(session, part_id)
    assert item is not None
    was_low = stock.is_low(item, await stock.levels(session, part_id))

    line_id = uuid.UUID(p["line_id"])
    reservation = await session.get(Reservation, line_id)
    if reservation is None:
        session.add(
            Reservation(
                line_id=line_id,
                order_id=uuid.UUID(p["order_id"]),
                order_number=p.get("order_number"),
                part_id=part_id,
                qty=_qty(p["qty"]),
                active=True,
                synced_at=at,
            )
        )
    elif reservation.synced_at < at:
        reservation.qty = _qty(p["qty"])
        reservation.active = True
        reservation.synced_at = at
    else:
        return []  # повтор або запізніла стара подія
    await session.flush()
    return await _low_signal(session, item, was_low)


async def on_parts_released(session: AsyncSession, event: dict[str, Any], at: datetime) -> Outgoing:
    p = event["payload"]
    line_id = uuid.UUID(p["line_id"])
    reservation = await session.get(Reservation, line_id)
    if reservation is None:
        # released прийшла раніше за reserved — лишаємо «надгробок», щоб
        # запізнілий reserved не створив резерв, якого вже не має бути.
        part_id = uuid.UUID(p["part_id"])
        await repository.upsert_item(
            session,
            part_id=part_id,
            sku=p["part_id"][:8],
            brand="",
            name="—",
            unit="pcs",
            synced_at=datetime.min.replace(tzinfo=at.tzinfo),
        )
        session.add(
            Reservation(
                line_id=line_id,
                order_id=uuid.UUID(p["order_id"]),
                part_id=part_id,
                qty=Decimal(0),
                active=False,
                synced_at=at,
            )
        )
    elif reservation.synced_at < at:
        reservation.active = False
        reservation.synced_at = at
    await session.flush()
    return []


async def _order_reservations(
    session: AsyncSession, order_id: uuid.UUID, at: datetime
) -> list[Reservation]:
    result = await session.execute(
        select(Reservation)
        .where(
            Reservation.order_id == order_id,
            Reservation.active.is_(True),
            Reservation.synced_at < at,
        )
        .order_by(Reservation.part_id)  # однаковий порядок блокувань — без взаємоблокувань
    )
    return list(result.scalars().all())


async def on_order_cancelled(
    session: AsyncSession, event: dict[str, Any], at: datetime
) -> Outgoing:
    for reservation in await _order_reservations(session, uuid.UUID(event["payload"]["id"]), at):
        reservation.active = False
        reservation.synced_at = at
    await session.flush()
    return []


async def on_order_closed(session: AsyncSession, event: dict[str, Any], at: datetime) -> Outgoing:
    """
    Авто видано — зарезервовані деталі списуються з найстаріших партій.

    Повтор події нічого не спише вдруге: резерви вже неактивні, а на рядок
    наряду є унікальний рух `issue`.
    """
    payload = event["payload"]
    order_id = uuid.UUID(payload["id"])
    out: Outgoing = []
    for reservation in await _order_reservations(session, order_id, at):
        item = await stock.lock(session, reservation.part_id)
        assert item is not None
        was_low = stock.is_low(item, await stock.levels(session, item.part_id))

        result = await stock.write_off(
            session,
            item,
            qty=reservation.qty,
            kind="issue",
            now=at,
            order_id=order_id,
            order_number=payload.get("number") or reservation.order_number,
            line_id=reservation.line_id,
        )
        reservation.active = False
        reservation.synced_at = at

        out.append(
            (
                "stock.issued",
                {
                    "order_id": str(order_id),
                    "line_id": str(reservation.line_id),
                    "part_id": str(item.part_id),
                    "qty": f"{result.issued:.3f}",
                    "cost": f"{result.cost:.2f}",
                },
            )
        )
        if result.short > 0:
            # Авто вже поїхало з деталлю, а за обліком її не було: облік хибний.
            out.append(
                (
                    "stock.discrepancy",
                    {
                        "part_id": str(item.part_id),
                        "order_id": str(order_id),
                        "short": f"{result.short:.3f}",
                    },
                )
            )
        await session.flush()
        out += await _low_signal(session, item, was_low)
    return out


async def on_purchase_received(
    session: AsyncSession, event: dict[str, Any], at: datetime
) -> Outgoing:
    """
    Прихід за накладною постачальника — від procurement.

    Кожен рядок приходу стає партією один раз: рух `receipt` з line_id рядка
    приходу унікальний, тож повтор події партій не подвоїть.
    """
    p = event["payload"]
    note = f"{p['number']} · {p['supplier']}"
    if p.get("invoice_number"):
        note += f" · накл. {p['invoice_number']}"
    out: Outgoing = []
    for line in sorted(p["lines"], key=lambda x: x["part_id"]):
        line_id = uuid.UUID(line["receipt_line_id"])
        done = await session.scalar(
            select(Movement.id).where(Movement.kind == "receipt", Movement.line_id == line_id)
        )
        if done is not None:
            continue
        part_id = uuid.UUID(line["part_id"])
        await repository.upsert_item(
            session,
            part_id=part_id,
            sku=line["sku"],
            brand=line["brand"],
            name=line["name"],
            unit=line["unit"],
            synced_at=datetime.min.replace(tzinfo=at.tzinfo),
        )
        item = await stock.lock(session, part_id)
        assert item is not None
        qty, cost = _qty(line["qty"]), Decimal(line["unit_cost"])
        await stock.receive(
            session,
            item,
            qty=qty,
            unit_cost=cost,
            source="receipt",
            note=note[:200],
            now=at,
            line_id=line_id,
        )
        lv = await stock.levels(session, part_id)
        out.append(("stock.received", stock.received_payload(item, lv, qty, cost)))
    return out


HANDLERS = {
    "part.created": on_part_upsert,
    "part.updated": on_part_upsert,
    "parts.reserved": on_parts_reserved,
    "parts.released": on_parts_released,
    "order.cancelled": on_order_cancelled,
    "order.closed": on_order_closed,
    "purchase.received": on_purchase_received,
}
