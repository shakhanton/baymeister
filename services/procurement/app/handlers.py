"""
Реакції на події складу.

Брокер гарантує at-least-once і не гарантує порядок, тому обробники
ідемпотентні, а старіша подія не перезаписує новішу — порівнюється час події
з `Need.synced_at`.

- `stock.low` — заводить потребу. Якщо деталь уже купували, вона сама йде в
  чернетку замовлення тому ж постачальнику за останньою ціною; якщо ні —
  чекає в списку потреб, поки хтось обере постачальника.
- `stock.received` — прихід підняв залишок вище мінімуму: потребу закрито.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import repository
from app.models import Need

Outgoing = list[tuple[str, dict[str, Any]]]


def _qty(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.001"))


async def on_stock_low(session: AsyncSession, event: dict[str, Any], at: datetime) -> Outgoing:
    p = event["payload"]
    part_id = uuid.UUID(p["part_id"])
    need = await session.get(Need, part_id)
    if need is not None and need.synced_at >= at:
        return []  # повтор або запізніла стара подія

    if need is None:
        need = Need(part_id=part_id, raised_at=at)
        session.add(need)
    elif not need.open:
        need.raised_at = at
    need.sku, need.brand, need.name = p["sku"], p["brand"], p["name"]
    need.unit = p.get("unit") or "pcs"
    need.free, need.min_qty = _qty(p["free"]), _qty(p["min_qty"])
    need.open = True
    need.synced_at = at
    await session.flush()

    # Деталь уже замовлена чи в чернетці — вдруге не додаємо.
    if await repository.active_order(session, part_id) is not None:
        return []
    last = await repository.last_line(session, part_id)
    if last is None:
        return []
    line, supplier = last
    await repository.add_need_to_draft(
        session, need, supplier, at, auto=True, unit_cost=line.unit_cost
    )
    return []


async def on_stock_received(session: AsyncSession, event: dict[str, Any], at: datetime) -> Outgoing:
    p = event["payload"]
    need = await session.get(Need, uuid.UUID(p["part_id"]))
    if need is None or need.synced_at >= at:
        return []
    need.synced_at = at
    if "free" in p:
        need.free = _qty(p["free"])
    # Старий склад не надсилав `low` — вважаємо, що прихід потребу закрив.
    if not p.get("low", False):
        need.open = False
    await session.flush()
    return []


HANDLERS = {
    "stock.low": on_stock_low,
    "stock.received": on_stock_received,
}
