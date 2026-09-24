"""Копії клієнта й авто на дошці оновлюються подіями — ідемпотентно й за часом."""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import repository
from tests.conftest import GOLF, PETRENKO
from tests.test_scheduling import booking


async def test_customer_and_vehicle_copies_follow_events(
    client: AsyncClient, session: AsyncSession, lift: str
) -> None:
    created = (
        await client.post(
            "/scheduling/appointments", json=booking(lift, (10, 0), (11, 0), vehicle_id=GOLF)
        )
    ).json()
    later = datetime.now(UTC) + timedelta(seconds=5)

    assert (
        await repository.apply_customer_update(
            session,
            customer_id=uuid.UUID(PETRENKO),
            name="Петренко І.",
            phone="+380670000000",
            occurred_at=later,
        )
        == 1
    )
    assert (
        await repository.apply_vehicle_update(
            session,
            vehicle_id=uuid.UUID(GOLF),
            label="KA0001AA · Volkswagen Golf",
            occurred_at=later,
        )
        == 1
    )
    await session.commit()

    body = (await client.get(f"/scheduling/appointments/{created['id']}")).json()
    assert body["customer_name"] == "Петренко І."
    assert body["vehicle_label"] == "KA0001AA · Volkswagen Golf"

    # Повтор тієї самої події й запізніла стара — нічого не змінюють.
    assert (
        await repository.apply_vehicle_update(
            session, vehicle_id=uuid.UUID(GOLF), label="старе", occurred_at=later
        )
        == 0
    )
    assert (
        await repository.apply_customer_update(
            session,
            customer_id=uuid.UUID(PETRENKO),
            name="старе",
            phone="+380670000001",
            occurred_at=later - timedelta(seconds=3),
        )
        == 0
    )
