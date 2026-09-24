from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import GOLF, KOVAL, PETRENKO, FakePeers, as_user

TOMORROW = (datetime.now(UTC) + timedelta(days=1)).replace(
    hour=0, minute=0, second=0, microsecond=0
)


def at(hour: int, minute: int = 0) -> str:
    return (TOMORROW + timedelta(hours=hour, minutes=minute)).isoformat()


def booking(bay: str, start: tuple[int, int], end: tuple[int, int], **extra: Any) -> dict[str, Any]:
    return {
        "bay_id": bay,
        "customer_id": PETRENKO,
        "starts_at": at(*start),
        "ends_at": at(*end),
        **extra,
    }


async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200


# ── Пости ───────────────────────────────────────────────────────────────────


async def test_bays_are_ordered_by_position(client: AsyncClient) -> None:
    await client.post(
        "/scheduling/bays", json={"name": "Стенд", "kind": "alignment", "position": 20}
    )
    await client.post(
        "/scheduling/bays", json={"name": "Підйомник", "kind": "lift", "position": 10}
    )

    bays = (await client.get("/scheduling/bays")).json()
    assert [b["name"] for b in bays] == ["Підйомник", "Стенд"]


async def test_duplicate_bay_name_is_409(client: AsyncClient, lift: str) -> None:
    response = await client.post("/scheduling/bays", json={"name": "Підйомник 1", "kind": "pit"})
    assert response.status_code == 409


async def test_bay_with_future_bookings_cannot_be_archived(client: AsyncClient, lift: str) -> None:
    await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))

    response = await client.post(f"/scheduling/bays/{lift}/archive")
    assert response.status_code == 409
    assert "майбутні записи" in response.json()["detail"]


# ── Запис ───────────────────────────────────────────────────────────────────


async def test_booking_copies_customer_and_vehicle(client: AsyncClient, lift: str) -> None:
    response = await client.post(
        "/scheduling/appointments", json=booking(lift, (10, 0), (11, 30), vehicle_id=GOLF)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "booked"
    assert body["customer_name"] == "Петренко Іван"
    assert body["vehicle_label"] == "AA1234BC · Volkswagen Golf"


async def test_overlap_on_same_bay_is_409_with_who_holds_it(client: AsyncClient, lift: str) -> None:
    await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))

    response = await client.post(
        "/scheduling/appointments",
        json={**booking(lift, (10, 30), (12, 0)), "customer_id": KOVAL},
    )
    assert response.status_code == 409
    assert "Підйомник 1 зайнятий" in response.json()["detail"]
    assert "Петренко" in response.json()["detail"]


async def test_back_to_back_bookings_do_not_clash(client: AsyncClient, lift: str) -> None:
    await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))
    response = await client.post("/scheduling/appointments", json=booking(lift, (11, 0), (12, 0)))
    assert response.status_code == 201


async def test_same_time_on_another_bay_is_fine(client: AsyncClient, lift: str) -> None:
    pit = (await client.post("/scheduling/bays", json={"name": "Яма", "kind": "pit"})).json()["id"]
    await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))
    response = await client.post("/scheduling/appointments", json=booking(pit, (10, 0), (11, 0)))
    assert response.status_code == 201


async def test_cancelled_booking_frees_the_slot(client: AsyncClient, lift: str) -> None:
    first = (
        await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))
    ).json()
    await client.post(
        f"/scheduling/appointments/{first['id']}/status", json={"status": "cancelled"}
    )

    response = await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))
    assert response.status_code == 201


async def test_period_rules(client: AsyncClient, lift: str) -> None:
    backwards = await client.post("/scheduling/appointments", json=booking(lift, (11, 0), (10, 0)))
    assert backwards.status_code == 422

    too_long = await client.post("/scheduling/appointments", json=booking(lift, (6, 0), (19, 0)))
    assert too_long.status_code == 422

    naive = {**booking(lift, (10, 0), (11, 0)), "starts_at": "2030-01-01T10:00:00"}
    assert (await client.post("/scheduling/appointments", json=naive)).status_code == 422


async def test_vehicle_of_another_customer_is_rejected(client: AsyncClient, lift: str) -> None:
    response = await client.post(
        "/scheduling/appointments",
        json={**booking(lift, (10, 0), (11, 0), vehicle_id=GOLF), "customer_id": KOVAL},
    )
    assert response.status_code == 422
    assert "іншому клієнту" in response.json()["detail"]


async def test_unknown_customer_and_archived_bay(client: AsyncClient, lift: str) -> None:
    unknown = {
        **booking(lift, (10, 0), (11, 0)),
        "customer_id": "99999999-9999-9999-9999-999999999999",
    }
    assert (await client.post("/scheduling/appointments", json=unknown)).status_code == 422

    await client.post(f"/scheduling/bays/{lift}/archive")
    gone = await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))
    assert gone.status_code == 422


async def test_vehicles_down_is_503(client: AsyncClient, lift: str, peers: FakePeers) -> None:
    peers.down.add("vehicles")
    response = await client.post(
        "/scheduling/appointments", json=booking(lift, (10, 0), (11, 0), vehicle_id=GOLF)
    )
    assert response.status_code == 503
    assert "Автомобілі" in response.json()["detail"]


async def test_clash_is_checked_before_calling_neighbours(
    client: AsyncClient, lift: str, peers: FakePeers
) -> None:
    await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))
    calls = len(peers.requests)

    await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))
    assert len(peers.requests) == calls


# ── Перенесення й статуси ───────────────────────────────────────────────────


async def test_reschedule_checks_new_slot_but_ignores_itself(
    client: AsyncClient, lift: str
) -> None:
    a = (await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))).json()
    await client.post("/scheduling/appointments", json=booking(lift, (12, 0), (13, 0)))

    # Подовжити в межах власного слоту — не конфлікт із самим собою.
    longer = await client.patch(f"/scheduling/appointments/{a['id']}", json={"ends_at": at(11, 30)})
    assert longer.status_code == 200

    clash = await client.patch(
        f"/scheduling/appointments/{a['id']}", json={"starts_at": at(12, 30), "ends_at": at(13, 30)}
    )
    assert clash.status_code == 409


async def test_status_transitions(client: AsyncClient, lift: str) -> None:
    a = (await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))).json()
    url = f"/scheduling/appointments/{a['id']}/status"

    assert (await client.post(url, json={"status": "completed"})).status_code == 409
    assert (await client.post(url, json={"status": "arrived"})).json()["status"] == "arrived"

    # Приїхав — переносити пізно.
    moved = await client.patch(f"/scheduling/appointments/{a['id']}", json={"starts_at": at(9, 0)})
    assert moved.status_code == 409

    assert (await client.post(url, json={"status": "completed"})).json()["status"] == "completed"
    final = await client.post(url, json={"status": "cancelled"})
    assert final.status_code == 409
    assert "завершений" in final.json()["detail"]


# ── Дошка ───────────────────────────────────────────────────────────────────


async def test_day_board_lists_what_overlaps_the_range(client: AsyncClient, lift: str) -> None:
    await client.post("/scheduling/appointments", json=booking(lift, (9, 0), (10, 0)))
    late = (
        await client.post("/scheduling/appointments", json=booking(lift, (23, 0), (23, 30)))
    ).json()
    cancelled = (
        await client.post("/scheduling/appointments", json=booking(lift, (15, 0), (16, 0)))
    ).json()
    await client.post(
        f"/scheduling/appointments/{cancelled['id']}/status", json={"status": "cancelled"}
    )

    day = await client.get("/scheduling/appointments", params={"from": at(0), "to": at(24)})
    assert [a["starts_at"][11:16] for a in day.json()] == ["09:00", "23:00"]

    with_cancelled = await client.get(
        "/scheduling/appointments",
        params={"from": at(0), "to": at(24), "include_cancelled": True},
    )
    assert len(with_cancelled.json()) == 3

    morning = await client.get("/scheduling/appointments", params={"from": at(8), "to": at(12)})
    assert late["id"] not in {a["id"] for a in morning.json()}


async def test_range_is_limited(client: AsyncClient) -> None:
    response = await client.get(
        "/scheduling/appointments", params={"from": at(0), "to": at(24 * 40)}
    )
    assert response.status_code == 422


# ── Права ───────────────────────────────────────────────────────────────────


async def test_mechanic_sees_board_but_cannot_book(client: AsyncClient, lift: str) -> None:
    mechanic = as_user("scheduling.read,customers.read,vehicles.read")
    assert (await client.get("/scheduling/bays", headers=mechanic)).status_code == 200
    denied = await client.post(
        "/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)), headers=mechanic
    )
    assert denied.status_code == 403


async def test_race_loser_gets_409_not_500(
    client: AsyncClient, lift: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Два запити пройшли перевірку одночасно — другого зупиняє exclusion
    constraint Postgres уже на INSERT (flush). SQLite такого constraint не має,
    тому відмову бази імітуємо; на Postgres це перевірено гонкою з 40 запитів.
    """
    from sqlalchemy.exc import IntegrityError

    from app import repository

    async def taken(*_: object, **__: object) -> None:
        raise IntegrityError("INSERT", {}, Exception("ex_appointments_bay_no_overlap"))

    monkeypatch.setattr(repository, "create", taken)
    response = await client.post("/scheduling/appointments", json=booking(lift, (10, 0), (11, 0)))

    assert response.status_code == 409
    assert "щойно зайняли" in response.json()["detail"]


async def test_conflict_message_uses_business_timezone(client: AsyncClient, lift: str) -> None:
    """Дошка показує місцевий час — повідомлення про конфлікт мусить казати те саме."""
    kyiv_10 = "2031-07-01T10:00:00+03:00"
    body = {
        "bay_id": lift,
        "customer_id": PETRENKO,
        "starts_at": kyiv_10,
        "ends_at": "2031-07-01T11:00:00+03:00",
    }
    await client.post("/scheduling/appointments", json=body)

    clash = await client.post("/scheduling/appointments", json=body)
    assert "з 01.07 10:00 до 01.07 11:00" in clash.json()["detail"]
    assert "UTC" not in clash.json()["detail"]
