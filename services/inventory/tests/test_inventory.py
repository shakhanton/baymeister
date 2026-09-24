from typing import Any

from httpx import AsyncClient

from tests.conftest import FILTER, OIL, Clock, Deliver, as_user, new_id, reserved


async def stock_of(client: AsyncClient, part: str) -> Any:
    return (await client.get(f"/inventory/stock/{part}")).json()


async def receive(client: AsyncClient, part: str, qty: str, cost: str) -> Any:
    return await client.post(
        "/inventory/receipts", json={"part_id": part, "qty": qty, "unit_cost": cost}
    )


async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200


# ── Прихід і FIFO ───────────────────────────────────────────────────────────


async def test_receipt_opens_card_from_catalog(client: AsyncClient) -> None:
    response = await receive(client, FILTER, "10", "180")
    assert response.status_code == 201
    body = response.json()
    assert (body["brand"], body["sku"], body["name"]) == ("MAHLE", "OC90", "Фільтр оливний")
    assert (body["on_hand"], body["free"], body["value"]) == ("10.000", "10.000", "1800.00")


async def test_unknown_part_and_zero_qty_are_refused(client: AsyncClient) -> None:
    unknown = await receive(client, "9a000000-0000-0000-0000-00000000dead", "1", "1")
    assert unknown.status_code == 422
    assert (await receive(client, FILTER, "0", "1")).status_code == 422


async def test_closed_order_writes_off_oldest_lots_first(
    client: AsyncClient, deliver: Deliver
) -> None:
    await receive(client, FILTER, "10", "100")
    await receive(client, FILTER, "10", "120")
    order, line = new_id(), new_id()

    await deliver("parts.reserved", reserved(line, order, FILTER, "15"))
    mid = await stock_of(client, FILTER)
    assert (mid["on_hand"], mid["reserved"], mid["free"]) == ("20.000", "15.000", "5.000")

    out = await deliver("order.closed", {"id": order, "number": "2026-00001"})

    # 10 × 100 з першої партії + 5 × 120 з другої.
    issued = next(p for e, p in out if e == "stock.issued")
    assert (issued["qty"], issued["cost"]) == ("15.000", "1600.00")
    after = await stock_of(client, FILTER)
    assert (after["on_hand"], after["reserved"], after["value"]) == ("5.000", "0.000", "600.00")
    assert [lot["unit_cost"] for lot in after["lots"]] == ["120.00"]
    assert after["movements"][0]["kind"] == "issue"
    assert after["movements"][0]["order_number"] == "2026-00001"


# ── Надійність подій ────────────────────────────────────────────────────────


async def test_redelivered_events_change_nothing(
    client: AsyncClient, deliver: Deliver, clock: Clock
) -> None:
    await receive(client, FILTER, "10", "100")
    order, line = new_id(), new_id()
    at_reserve, at_close = clock.tick(), clock.tick()

    await deliver("parts.reserved", reserved(line, order, FILTER, "3"), at_reserve)
    await deliver("parts.reserved", reserved(line, order, FILTER, "3"), at_reserve)
    await deliver("order.closed", {"id": order}, at_close)
    again = await deliver("order.closed", {"id": order}, at_close)

    assert again == []
    body = await stock_of(client, FILTER)
    assert body["on_hand"] == "7.000"
    assert [m["kind"] for m in body["movements"]].count("issue") == 1


async def test_quantity_change_uses_newest_event(
    client: AsyncClient, deliver: Deliver, clock: Clock
) -> None:
    order, line = new_id(), new_id()
    t1, t2, t3 = clock.tick(), clock.tick(), clock.tick()

    await deliver("parts.reserved", reserved(line, order, OIL, "4"), t1)
    await deliver("parts.reserved", reserved(line, order, OIL, "5"), t3)
    # Запізніла подія з кількістю між ними — старіша, ігнорується.
    await deliver("parts.reserved", reserved(line, order, OIL, "4.5"), t2)

    assert (await stock_of(client, OIL))["reserved"] == "5.000"


async def test_release_before_reserve_leaves_no_ghost_reservation(
    client: AsyncClient, deliver: Deliver, clock: Clock
) -> None:
    order, line = new_id(), new_id()
    t_reserve, t_release = clock.tick(), clock.tick()

    await deliver(
        "parts.released", {"order_id": order, "line_id": line, "part_id": FILTER}, t_release
    )
    await deliver("parts.reserved", reserved(line, order, FILTER, "2"), t_reserve)

    assert (await stock_of(client, FILTER))["reserved"] == "0.000"


async def test_cancelled_order_releases_reservations(client: AsyncClient, deliver: Deliver) -> None:
    order = new_id()
    await deliver("parts.reserved", reserved(new_id(), order, FILTER, "2"))
    await deliver("parts.reserved", reserved(new_id(), order, OIL, "4"))
    await deliver("order.cancelled", {"id": order})

    assert (await stock_of(client, FILTER))["reserved"] == "0.000"
    assert (await stock_of(client, OIL))["reserved"] == "0.000"


async def test_short_stock_is_issued_partially_and_flagged(
    client: AsyncClient, deliver: Deliver
) -> None:
    await receive(client, FILTER, "3", "100")
    order = new_id()
    await deliver("parts.reserved", reserved(new_id(), order, FILTER, "5"))
    out = await deliver("order.closed", {"id": order})

    assert ("stock.discrepancy", {"part_id": FILTER, "order_id": order, "short": "2.000"}) in out
    body = await stock_of(client, FILTER)
    assert body["on_hand"] == "0.000"
    assert "Не вистачило 2.000" in body["movements"][0]["note"]


# ── Мінімальний залишок ─────────────────────────────────────────────────────


async def test_low_stock_signal_fires_once_on_crossing(
    client: AsyncClient, deliver: Deliver
) -> None:
    await receive(client, FILTER, "10", "100")
    await client.patch(f"/inventory/stock/{FILTER}", json={"min_qty": "4", "location": "A-03-2"})

    order = new_id()
    first = await deliver("parts.reserved", reserved(new_id(), order, FILTER, "5"))
    assert first == []  # вільних 5 ≥ 4
    crossing = await deliver("parts.reserved", reserved(new_id(), order, FILTER, "2"))
    assert [e for e, _ in crossing] == ["stock.low"]  # вільних 3 < 4
    below = await deliver("parts.reserved", reserved(new_id(), order, FILTER, "1"))
    assert below == []  # уже нижче — не спамимо

    low = (await client.get("/inventory/stock", params={"low": True})).json()
    assert [i["sku"] for i in low["items"]] == ["OC90"]
    assert low["items"][0]["location"] == "A-03-2"


async def test_free_can_go_negative_as_a_buy_signal(client: AsyncClient, deliver: Deliver) -> None:
    await receive(client, OIL, "2", "300")
    await deliver("parts.reserved", reserved(new_id(), new_id(), OIL, "4,5".replace(",", ".")))
    assert (await stock_of(client, OIL))["free"] == "-2.500"


# ── Інвентаризація ──────────────────────────────────────────────────────────


async def test_count_shortage_and_surplus(client: AsyncClient) -> None:
    await receive(client, FILTER, "5", "100")
    await receive(client, FILTER, "5", "120")

    short = await client.post(f"/inventory/stock/{FILTER}/count", json={"counted": "7"})
    # Мінус 3 з найстарішої партії: лишилось 2 × 100 + 5 × 120.
    assert (short.json()["on_hand"], short.json()["value"]) == ("7.000", "800.00")

    surplus = await client.post(f"/inventory/stock/{FILTER}/count", json={"counted": "8"})
    body = surplus.json()
    assert body["on_hand"] == "8.000"
    assert body["value"] == "920.00"  # +1 за ціною останнього приходу (120)

    kinds = [m["kind"] for m in (await stock_of(client, FILTER))["movements"]]
    assert kinds[:2] == ["count_plus", "count_minus"]


async def test_catalog_events_keep_the_card_fresh(client: AsyncClient, deliver: Deliver) -> None:
    await receive(client, FILTER, "1", "100")
    await deliver(
        "part.updated",
        {"id": FILTER, "sku": "OC90", "brand": "MAHLE", "name": "Фільтр оливи OC90", "unit": "pcs"},
    )
    assert (await stock_of(client, FILTER))["name"] == "Фільтр оливи OC90"


# ── Права ───────────────────────────────────────────────────────────────────


async def test_manager_reads_stock_but_cannot_receive(client: AsyncClient) -> None:
    manager = as_user("inventory.read,catalog.read")
    assert (await client.get("/inventory/stock", headers=manager)).status_code == 200
    denied = await client.post(
        "/inventory/receipts",
        json={"part_id": FILTER, "qty": "1", "unit_cost": "1"},
        headers=manager,
    )
    assert denied.status_code == 403


# ── Прихід від procurement ──────────────────────────────────────────────────


def purchase(lines: list[tuple[str, str, str, str]]) -> dict[str, Any]:
    """lines: (receipt_line_id, part, qty, unit_cost)."""
    return {
        "order_id": new_id(),
        "number": "PO-2026-00007",
        "supplier": "Автотехнікс",
        "invoice_number": "РН-118",
        "lines": [
            {
                "receipt_line_id": rid,
                "part_id": part,
                "sku": "OC90" if part == FILTER else "5W30-1L",
                "brand": "MAHLE" if part == FILTER else "CASTROL",
                "name": "Фільтр оливний" if part == FILTER else "Олива 5W-30",
                "unit": "pcs" if part == FILTER else "l",
                "qty": qty,
                "unit_cost": cost,
            }
            for rid, part, qty, cost in lines
        ],
    }


async def test_purchase_receipt_opens_cards_and_is_applied_once(
    client: AsyncClient, deliver: Deliver, clock: Clock
) -> None:
    event = purchase([(new_id(), FILTER, "6", "175.50"), (new_id(), OIL, "20", "310")])
    at = clock.tick()
    out = await deliver("purchase.received", event, at)
    again = await deliver("purchase.received", event, at)

    assert [e for e, _ in out] == ["stock.received", "stock.received"]
    assert again == []
    body = await stock_of(client, FILTER)
    assert (body["on_hand"], body["value"], body["name"]) == ("6.000", "1053.00", "Фільтр оливний")
    assert body["lots"][0]["note"] == "PO-2026-00007 · Автотехнікс · накл. РН-118"
    assert (await stock_of(client, OIL))["on_hand"] == "20.000"


async def test_received_tells_whether_part_is_still_low(
    client: AsyncClient, deliver: Deliver
) -> None:
    await receive(client, FILTER, "1", "100")
    await client.patch(f"/inventory/stock/{FILTER}", json={"min_qty": "5"})

    out = await deliver("purchase.received", purchase([(new_id(), FILTER, "2", "100")]))
    assert (out[0][1]["free"], out[0][1]["low"]) == ("3.000", True)
    out = await deliver("purchase.received", purchase([(new_id(), FILTER, "4", "100")]))
    assert (out[0][1]["free"], out[0][1]["low"]) == ("7.000", False)


async def test_low_signal_carries_unit_for_procurement(
    client: AsyncClient, deliver: Deliver
) -> None:
    await receive(client, OIL, "5", "300")
    await client.patch(f"/inventory/stock/{OIL}", json={"min_qty": "4"})
    out = await deliver("parts.reserved", reserved(new_id(), new_id(), OIL, "2"))
    assert out == [
        (
            "stock.low",
            {
                "part_id": OIL,
                "sku": "5W30-1L",
                "brand": "CASTROL",
                "name": "Олива 5W-30",
                "unit": "l",
                "free": "3.000",
                "min_qty": "4.000",
            },
        )
    ]
