from typing import Any

from httpx import AsyncClient

from tests.conftest import (
    DIAG,
    FILTER,
    GOLF,
    KOVAL,
    OIL_5W30,
    OIL_CHANGE,
    OLD_SERVICE,
    PETRENKO,
    FakePeers,
    as_user,
)


async def add(
    client: AsyncClient, order: dict[str, Any], kind: str, item: str, qty: str = "1"
) -> Any:
    return await client.post(
        f"/work-orders/{order['id']}/lines", json={"kind": kind, "catalog_id": item, "qty": qty}
    )


async def status(client: AsyncClient, order: dict[str, Any], to: str) -> Any:
    return await client.post(f"/work-orders/{order['id']}/status", json={"status": to})


async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200


# ── Відкриття ───────────────────────────────────────────────────────────────


async def test_open_copies_customer_vehicle_and_discount(order: dict[str, Any]) -> None:
    assert order["status"] == "open"
    assert order["customer_name"] == "Петренко Іван"
    assert order["vehicle_label"] == "AA1234BC · Volkswagen Golf"
    assert order["totals"]["discount_percent"] == "5.00"
    assert order["totals"]["total"] == "0.00"
    assert order["lines"] == []


async def test_numbers_are_sequential_within_the_year(
    client: AsyncClient, order: dict[str, Any]
) -> None:
    second = (
        await client.post("/work-orders", json={"customer_id": PETRENKO, "vehicle_id": GOLF})
    ).json()

    year, seq = order["number"].split("-")
    assert len(seq) == 5
    assert second["number"] == f"{year}-{int(seq) + 1:05d}"


async def test_vehicle_must_belong_to_customer(client: AsyncClient) -> None:
    response = await client.post("/work-orders", json={"customer_id": KOVAL, "vehicle_id": GOLF})
    assert response.status_code == 422
    assert "іншому клієнту" in response.json()["detail"]


async def test_neighbour_down_is_503_named(client: AsyncClient, peers: FakePeers) -> None:
    peers.down.add("vehicles")
    response = await client.post("/work-orders", json={"customer_id": PETRENKO, "vehicle_id": GOLF})
    assert response.status_code == 503
    assert "Автомобілі" in response.json()["detail"]


# ── Рядки й суми ────────────────────────────────────────────────────────────


async def test_line_prices_come_from_catalog_and_totals_add_up(
    client: AsyncClient, order: dict[str, Any]
) -> None:
    await add(client, order, "service", OIL_CHANGE)
    await add(client, order, "part", FILTER)
    body = (await add(client, order, "part", OIL_5W30, "4,5")).json()

    lines = {x["code"]: x for x in body["lines"]}
    assert lines["ENG-OIL"]["unit_price"] == "1147.50"
    assert lines["MAHLE OC90"]["amount"] == "245.50"
    assert lines["CASTROL 5W30-1L"]["qty"] == "4.500"
    assert lines["CASTROL 5W30-1L"]["amount"] == "1440.00"  # 4.5 × 320

    t = body["totals"]
    assert t["services"] == "1147.50"
    assert t["parts"] == "1685.50"
    assert t["subtotal"] == "2833.00"
    assert t["discount"] == "141.65"  # 5 % від 2833.00
    assert t["total"] == "2691.35"
    assert body["total"] == "2691.35"


async def test_price_is_frozen_when_catalog_changes(
    client: AsyncClient, order: dict[str, Any], peers: FakePeers
) -> None:
    await add(client, order, "service", OIL_CHANGE)
    peers.services[OIL_CHANGE]["price"] = "9999.00"

    body = (await client.get(f"/work-orders/{order['id']}")).json()
    assert body["lines"][0]["unit_price"] == "1147.50"


async def test_discount_is_frozen_at_opening(
    client: AsyncClient, order: dict[str, Any], peers: FakePeers
) -> None:
    peers.customers[PETRENKO]["discount_percent"] = 50
    await add(client, order, "part", FILTER)

    body = (await client.get(f"/work-orders/{order['id']}")).json()
    assert body["totals"]["discount_percent"] == "5.00"


async def test_service_without_price_is_refused_with_a_hint(
    client: AsyncClient, order: dict[str, Any]
) -> None:
    response = await add(client, order, "service", DIAG)
    assert response.status_code == 422
    assert "нормо-години" in response.json()["detail"]


async def test_archived_or_unknown_catalog_items_are_refused(
    client: AsyncClient, order: dict[str, Any]
) -> None:
    assert (await add(client, order, "service", OLD_SERVICE)).status_code == 422
    unknown = await add(client, order, "part", "9a000000-0000-0000-0000-00000000dead")
    assert unknown.status_code == 422


async def test_qty_update_and_removal(client: AsyncClient, order: dict[str, Any]) -> None:
    body = (await add(client, order, "part", OIL_5W30, "4")).json()
    line = body["lines"][0]

    updated = await client.patch(
        f"/work-orders/{order['id']}/lines/{line['id']}", json={"qty": "5"}
    )
    assert updated.json()["lines"][0]["amount"] == "1600.00"

    zero = await client.patch(f"/work-orders/{order['id']}/lines/{line['id']}", json={"qty": "0"})
    assert zero.status_code == 422

    removed = await client.delete(f"/work-orders/{order['id']}/lines/{line['id']}")
    assert removed.json()["lines"] == []


async def test_adding_a_line_needs_catalog_read(client: AsyncClient, order: dict[str, Any]) -> None:
    response = await client.post(
        f"/work-orders/{order['id']}/lines",
        json={"kind": "part", "catalog_id": FILTER},
        headers=as_user("work_orders.read,work_orders.write"),
    )
    assert response.status_code == 403
    assert "catalog.read" in response.json()["detail"]


# ── Статуси ─────────────────────────────────────────────────────────────────


async def test_full_lifecycle(client: AsyncClient, order: dict[str, Any]) -> None:
    await add(client, order, "service", OIL_CHANGE)

    assert (await status(client, order, "in_progress")).json()["status"] == "in_progress"
    done = (await status(client, order, "done")).json()
    assert done["status"] == "done" and done["done_at"]

    # Завершений наряд не редагується, але його можна повернути в роботу.
    assert (await add(client, order, "part", FILTER)).status_code == 409
    assert (await status(client, order, "in_progress")).json()["done_at"] is None
    await status(client, order, "done")

    closed = (await status(client, order, "closed")).json()
    assert closed["status"] == "closed" and closed["closed_at"]
    locked = await add(client, order, "part", FILTER)
    assert locked.status_code == 409
    assert "закрито" in locked.json()["detail"]


async def test_empty_order_cannot_be_done(client: AsyncClient, order: dict[str, Any]) -> None:
    await status(client, order, "in_progress")
    response = await status(client, order, "done")
    assert response.status_code == 409
    assert "скасувати" in response.json()["detail"]


async def test_illegal_transitions(client: AsyncClient, order: dict[str, Any]) -> None:
    assert (await status(client, order, "closed")).status_code == 409
    assert (await status(client, order, "cancelled")).status_code == 200
    assert (await status(client, order, "open")).status_code == 409


async def test_notes_can_be_added_after_closing_but_not_mileage(
    client: AsyncClient, order: dict[str, Any]
) -> None:
    await add(client, order, "service", OIL_CHANGE)
    for s in ("in_progress", "done", "closed"):
        await status(client, order, s)

    notes = await client.patch(f"/work-orders/{order['id']}", json={"notes": "Клієнт задоволений"})
    assert notes.status_code == 200
    mileage = await client.patch(f"/work-orders/{order['id']}", json={"mileage_km": 1})
    assert mileage.status_code == 409


# ── Список ──────────────────────────────────────────────────────────────────


async def test_list_search_and_filters(client: AsyncClient, order: dict[str, Any]) -> None:
    await add(client, order, "part", FILTER)

    by_number = await client.get("/work-orders", params={"search": order["number"]})
    assert by_number.json()["total"] == 1
    # 5 % від 245.50 = 12.275 → 12.28 (половина вгору), до сплати 233.22.
    assert by_number.json()["items"][0]["total"] == "233.22"

    by_plate = await client.get("/work-orders", params={"search": "aa 1234"})
    assert by_plate.json()["total"] == 1

    assert (await client.get("/work-orders", params={"status": "closed"})).json()["total"] == 0
    assert (await client.get("/work-orders", params={"vehicle_id": GOLF})).json()["total"] == 1


async def test_mechanic_reads_but_cannot_open(client: AsyncClient) -> None:
    mechanic = as_user("work_orders.read,customers.read,vehicles.read,catalog.read")
    assert (await client.get("/work-orders", headers=mechanic)).status_code == 200
    denied = await client.post(
        "/work-orders", json={"customer_id": PETRENKO, "vehicle_id": GOLF}, headers=mechanic
    )
    assert denied.status_code == 403


async def test_part_events_carry_what_inventory_needs(
    client: AsyncClient, order: dict[str, Any], monkeypatch: Any
) -> None:
    """inventory резервує за подіями: і додавання, і зміна кількості — parts.reserved."""
    from app import events

    sent: list[tuple[str, dict[str, Any]]] = []

    async def capture(event: str, payload: dict[str, Any]) -> None:
        sent.append((event, payload))

    monkeypatch.setattr(events, "publish", capture)

    body = (await add(client, order, "part", OIL_5W30, "4")).json()
    line_id = body["lines"][0]["id"]
    await client.patch(f"/work-orders/{order['id']}/lines/{line_id}", json={"qty": "5"})
    await client.delete(f"/work-orders/{order['id']}/lines/{line_id}")

    reserved = [p for e, p in sent if e == "parts.reserved"]
    assert [p["qty"] for p in reserved] == ["4.000", "5.000"]
    assert reserved[0]["line_id"] == reserved[1]["line_id"] == line_id
    assert reserved[0]["name"] == "Олива 5W-30"
    assert reserved[0]["unit"] == "l"
    assert reserved[0]["order_number"] == order["number"]
    assert [e for e, _ in sent][-1] == "parts.released"
