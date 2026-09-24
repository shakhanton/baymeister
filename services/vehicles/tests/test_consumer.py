"""
Слухач `customer.updated`: копія власника оновлюється ідемпотентно і не
відкочується запізнілою подією. Брокер у тестах не потрібен — перевіряється
обробник і розбір повідомлення.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import consumer, repository
from tests.conftest import PETRENKO_ID

GOLF = {"customer_id": PETRENKO_ID, "plate": "AA1234BC", "make": "Volkswagen", "model": "Golf"}


def event(name: str, phone: str, occurred_at: datetime) -> dict[str, Any]:
    return {
        "event": "customer.updated",
        "occurred_at": occurred_at.isoformat(),
        "producer": "customers",
        "payload": {"id": PETRENKO_ID, "name": name, "phone": phone},
    }


async def apply(session: AsyncSession, e: dict[str, Any]) -> int:
    changed = await repository.apply_customer_update(
        session,
        customer_id=uuid.UUID(e["payload"]["id"]),
        name=e["payload"]["name"],
        phone=e["payload"]["phone"],
        occurred_at=datetime.fromisoformat(e["occurred_at"]),
    )
    await session.commit()
    return changed


async def test_update_refreshes_all_vehicles_of_the_customer(
    client: AsyncClient, session: AsyncSession
) -> None:
    await client.post("/vehicles", json=GOLF)
    await client.post("/vehicles", json={**GOLF, "plate": "AA0002BC", "model": "Passat"})

    later = datetime.now(UTC) + timedelta(seconds=5)
    assert await apply(session, event("Петренко І. М.", "+380670000000", later)) == 2

    items = (await client.get("/vehicles")).json()["items"]
    assert {v["customer_name"] for v in items} == {"Петренко І. М."}
    assert {v["customer_phone"] for v in items} == {"+380670000000"}


async def test_redelivery_is_harmless(client: AsyncClient, session: AsyncSession) -> None:
    await client.post("/vehicles", json=GOLF)
    e = event("Петренко І. М.", "+380670000000", datetime.now(UTC) + timedelta(seconds=5))

    assert await apply(session, e) == 1
    # Брокер доставив ту саму подію вдруге — нічого не змінюється.
    assert await apply(session, e) == 0


async def test_stale_event_does_not_roll_back_newer_data(
    client: AsyncClient, session: AsyncSession
) -> None:
    await client.post("/vehicles", json=GOLF)
    now = datetime.now(UTC)

    await apply(session, event("Нове імʼя", "+380670000002", now + timedelta(seconds=10)))
    # Старіша подія прийшла пізніше — порядок доставки не гарантований.
    assert (
        await apply(session, event("Старе імʼя", "+380670000001", now + timedelta(seconds=5))) == 0
    )

    vehicle = (await client.get("/vehicles")).json()["items"][0]
    assert vehicle["customer_name"] == "Нове імʼя"


async def test_event_older_than_the_vehicle_is_ignored(
    client: AsyncClient, session: AsyncSession
) -> None:
    await client.post("/vehicles", json=GOLF)

    # Подія з минулого: автомобіль створено пізніше, з уже свіжою копією.
    stale = event("Застаріле", "+380670000009", datetime.now(UTC) - timedelta(hours=1))
    assert await apply(session, stale) == 0


class FakeMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.outcome: str | None = None

    async def ack(self) -> None:
        self.outcome = "ack"

    async def nack(self, requeue: bool = True) -> None:
        self.outcome = f"nack(requeue={requeue})"

    async def reject(self, requeue: bool = False) -> None:
        self.outcome = f"reject(requeue={requeue})"


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []

    async def handler(e: dict[str, Any]) -> None:
        if e["payload"].get("fail"):
            raise RuntimeError("база недоступна")
        seen.append(e)

    monkeypatch.setitem(consumer.HANDLERS, "customer.updated", handler)
    return seen


async def test_handled_message_is_acked(recorded: list[dict[str, Any]]) -> None:
    message = FakeMessage(json.dumps(event("А", "+380670000000", datetime.now(UTC))).encode())
    await consumer.handle(message)  # type: ignore[arg-type]

    assert message.outcome == "ack"
    assert len(recorded) == 1


async def test_failed_handler_requeues(recorded: list[dict[str, Any]]) -> None:
    body = event("А", "+380670000000", datetime.now(UTC))
    body["payload"]["fail"] = True
    message = FakeMessage(json.dumps(body).encode())
    await consumer.handle(message)  # type: ignore[arg-type]

    assert message.outcome == "nack(requeue=True)"


async def test_garbage_is_rejected_not_requeued(recorded: list[dict[str, Any]]) -> None:
    # Повтор не виправить зіпсоване повідомлення — інакше воно крутиться вічно.
    for body in (b"not json", json.dumps({"event": "unknown.event"}).encode()):
        message = FakeMessage(body)
        await consumer.handle(message)  # type: ignore[arg-type]
        assert message.outcome == "reject(requeue=False)"
