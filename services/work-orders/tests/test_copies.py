"""Копії клієнта й авто в наряді оновлюються подіями — ідемпотентно й за часом."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import repository
from tests.conftest import GOLF, PETRENKO


async def test_copies_follow_events_but_prices_do_not(
    client: AsyncClient, session: AsyncSession, order: dict[str, Any]
) -> None:
    later = datetime.now(UTC) + timedelta(seconds=5)
    changed = await repository.apply_customer_update(
        session,
        customer_id=uuid.UUID(PETRENKO),
        name="Петренко І.",
        phone="+380670000000",
        occurred_at=later,
    )
    assert changed == 1
    changed = await repository.apply_vehicle_update(
        session, vehicle_id=uuid.UUID(GOLF), label="KA0001AA · Volkswagen Golf", occurred_at=later
    )
    assert changed == 1
    await session.commit()

    body = (await client.get(f"/work-orders/{order['id']}")).json()
    assert body["customer_name"] == "Петренко І."
    assert body["vehicle_label"] == "KA0001AA · Volkswagen Golf"
    # Знижка — не копія, а умова угоди: подією вона не змінюється.
    assert body["totals"]["discount_percent"] == "5.00"

    # Повтор і запізніла стара подія — нічого не змінюють.
    stale = later - timedelta(seconds=3)
    assert (
        await repository.apply_vehicle_update(
            session, vehicle_id=uuid.UUID(GOLF), label="старе", occurred_at=later
        )
        == 0
    )
    assert (
        await repository.apply_customer_update(
            session, customer_id=uuid.UUID(PETRENKO), name="старе", phone="+3800", occurred_at=stale
        )
        == 0
    )
