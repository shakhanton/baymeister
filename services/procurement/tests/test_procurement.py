from typing import Any

from httpx import AsyncClient

from tests.conftest import FILTER, OIL, Clock, Deliver, Published, as_user, low


async def supplier(client: AsyncClient, name: str = "Автотехнікс", **extra: Any) -> Any:
    response = await client.post("/procurement/suppliers", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def order_with(client: AsyncClient, lines: list[tuple[str, str, str]]) -> Any:
    """Відправлене замовлення з рядками (деталь, кількість, ціна)."""
    s = await supplier(client)
    order = (await client.post("/procurement/orders", json={"supplier_id": s["id"]})).json()
    for part, qty, cost in lines:
        r = await client.post(
            f"/procurement/orders/{order['id']}/lines",
            json={"part_id": part, "qty": qty, "unit_cost": cost},
        )
        assert r.status_code == 201, r.text
    r = await client.post(f"/procurement/orders/{order['id']}/status", json={"status": "ordered"})
    assert r.status_code == 200, r.text
    return r.json()


async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200


# ── Постачальники ───────────────────────────────────────────────────────────


async def test_supplier_name_is_unique_regardless_of_case(client: AsyncClient) -> None:
    await supplier(client, "Автотехнікс", edrpou="12345678", phone="+380501112233")
    dup = await client.post("/procurement/suppliers", json={"name": "автотехнікс"})
    assert dup.status_code == 409
    assert "уже є" in dup.json()["detail"]
    bad = await client.post("/procurement/suppliers", json={"name": "X", "edrpou": "123"})
    assert bad.status_code == 422


async def test_archived_supplier_is_hidden_and_gets_no_orders(client: AsyncClient) -> None:
    s = await supplier(client)
    await client.patch(f"/procurement/suppliers/{s['id']}", json={"active": False})

    assert (await client.get("/procurement/suppliers")).json()["total"] == 0
    assert (await client.get("/procurement/suppliers?archived=true")).json()["total"] == 1
    r = await client.post("/procurement/orders", json={"supplier_id": s["id"]})
    assert r.status_code == 422
    assert "в архіві" in r.json()["detail"]


# ── Замовлення ──────────────────────────────────────────────────────────────


async def test_draft_lines_snapshot_catalog_and_numbers_run_in_sequence(
    client: AsyncClient,
) -> None:
    s = await supplier(client)
    first = (await client.post("/procurement/orders", json={"supplier_id": s["id"]})).json()
    second = (await client.post("/procurement/orders", json={"supplier_id": s["id"]})).json()
    assert first["number"].startswith("PO-") and first["number"].endswith("-00001")
    assert second["number"].endswith("-00002")

    url = f"/procurement/orders/{first['id']}/lines"
    body = await client.post(url, json={"part_id": FILTER, "qty": "10", "unit_cost": "175,5"})
    order = body.json()
    assert (order["lines"][0]["name"], order["lines"][0]["unit"]) == ("Фільтр оливний", "pcs")
    assert order["total"] == "1755.00"

    dup = await client.post(url, json={"part_id": FILTER, "qty": "1", "unit_cost": "1"})
    assert dup.status_code == 409
    line = order["lines"][0]["id"]
    order = (await client.patch(f"{url}/{line}", json={"qty": "12"})).json()
    assert order["total"] == "2106.00"


async def test_sending_needs_lines_and_prices_then_locks_lines(
    client: AsyncClient, published: Published
) -> None:
    s = await supplier(client)
    order = (await client.post("/procurement/orders", json={"supplier_id": s["id"]})).json()
    status_url = f"/procurement/orders/{order['id']}/status"

    empty = await client.post(status_url, json={"status": "ordered"})
    assert empty.status_code == 409
    await client.post(
        f"/procurement/orders/{order['id']}/lines",
        json={"part_id": OIL, "qty": "20", "unit_cost": "0"},
    )
    unpriced = await client.post(status_url, json={"status": "ordered"})
    assert unpriced.status_code == 409
    assert "Олива 5W-30" in unpriced.json()["detail"]

    line = (await client.get(f"/procurement/orders/{order['id']}")).json()["lines"][0]["id"]
    await client.patch(f"/procurement/orders/{order['id']}/lines/{line}", json={"unit_cost": "310"})
    sent = await client.post(status_url, json={"status": "ordered"})
    assert sent.json()["status"] == "ordered"
    assert published[-1][0] == "purchase.ordered"
    assert published[-1][1]["total"] == "6200.00"

    locked = await client.delete(f"/procurement/orders/{order['id']}/lines/{line}")
    assert locked.status_code == 409


async def test_partial_receipts_feed_the_warehouse_and_close_the_order(
    client: AsyncClient, published: Published
) -> None:
    order = await order_with(client, [(FILTER, "10", "175.50"), (OIL, "20", "310")])
    f_line, o_line = (line["id"] for line in order["lines"])
    url = f"/procurement/orders/{order['id']}/receipts"

    first = await client.post(
        url,
        json={
            "invoice_number": "РН-118",
            "lines": [{"line_id": f_line, "qty": "6"}, {"line_id": o_line, "qty": "20"}],
        },
    )
    assert first.status_code == 201
    assert first.json()["status"] == "ordered"
    event, payload = published[-1]
    assert event == "purchase.received"
    assert (payload["number"], payload["supplier"]) == (order["number"], "Автотехнікс")
    assert [(x["sku"], x["qty"], x["unit_cost"]) for x in payload["lines"]] == [
        ("OC90", "6.000", "175.50"),
        ("5W30-1L", "20.000", "310.00"),
    ]
    assert len({x["receipt_line_id"] for x in payload["lines"]}) == 2

    too_much = await client.post(url, json={"lines": [{"line_id": f_line, "qty": "5"}]})
    assert too_much.status_code == 422
    assert too_much.json()["detail"] == "Фільтр оливний: замовлено 10, лишилось отримати 4"

    # Постачальник підняв ціну — у прихід іде фактична.
    last = await client.post(
        url, json={"lines": [{"line_id": f_line, "qty": "4", "unit_cost": "180"}]}
    )
    body = last.json()
    assert body["status"] == "received"
    assert [r["total"] for r in body["receipts"]] == ["7253.00", "720.00"]
    assert published[-1][1]["lines"][0]["unit_cost"] == "180.00"

    listed = (await client.get("/procurement/orders?status=received")).json()
    assert listed["items"][0]["received_share"] == 1.0


async def test_cancel_only_before_anything_arrived_then_close_short(
    client: AsyncClient,
) -> None:
    order = await order_with(client, [(FILTER, "10", "175.50")])
    line = order["lines"][0]["id"]
    status_url = f"/procurement/orders/{order['id']}/status"

    nothing = await client.post(status_url, json={"status": "received"})
    assert nothing.status_code == 409
    await client.post(
        f"/procurement/orders/{order['id']}/receipts",
        json={"lines": [{"line_id": line, "qty": "7"}]},
    )
    cancel = await client.post(status_url, json={"status": "cancelled"})
    assert cancel.status_code == 409
    short = await client.post(status_url, json={"status": "received"})
    assert short.json()["status"] == "received"
    assert short.json()["lines"][0]["qty_received"] == "7.000"


async def test_read_only_user_cannot_order(client: AsyncClient) -> None:
    r = await client.post(
        "/procurement/suppliers", json={"name": "X"}, headers=as_user("procurement.read")
    )
    assert r.status_code == 403


# ── Потреби від складу ──────────────────────────────────────────────────────


async def test_new_part_waits_for_a_supplier(client: AsyncClient, deliver: Deliver) -> None:
    await deliver("stock.low", low(FILTER, "1.000", "4.000"))
    needs = (await client.get("/procurement/needs")).json()
    assert [(n["sku"], n["free"], n["order"], n["last_supplier"]) for n in needs] == [
        ("OC90", "1.000", None, None)
    ]

    s = await supplier(client)
    order = (
        await client.post(f"/procurement/needs/{FILTER}/order", json={"supplier_id": s["id"]})
    ).json()
    # До двох мінімумів: 2 × 4 − 1 = 7; ціни ще не знаємо.
    assert (order["status"], order["lines"][0]["qty"], order["lines"][0]["unit_cost"]) == (
        "draft",
        "7.000",
        "0.00",
    )
    need = (await client.get("/procurement/needs")).json()[0]
    assert need["order"]["number"] == order["number"]
    again = await client.post(f"/procurement/needs/{FILTER}/order", json={"supplier_id": s["id"]})
    assert again.status_code == 409


async def test_known_part_goes_to_last_supplier_draft_by_itself(
    client: AsyncClient, deliver: Deliver
) -> None:
    order = await order_with(client, [(FILTER, "10", "175.50")])
    await client.post(
        f"/procurement/orders/{order['id']}/receipts",
        json={"lines": [{"line_id": order["lines"][0]["id"], "qty": "10"}]},
    )

    await deliver("stock.low", low(FILTER, "2.000", "5.000"))
    await deliver("stock.low", low(OIL, "0.500", "2.000"))  # нову деталь не чіпаємо

    drafts = (await client.get("/procurement/orders?status=draft")).json()["items"]
    assert len(drafts) == 1 and drafts[0]["auto"] is True
    draft = (await client.get(f"/procurement/orders/{drafts[0]['id']}")).json()
    assert [(x["sku"], x["qty"], x["unit_cost"]) for x in draft["lines"]] == [
        ("OC90", "8.000", "175.50")
    ]
    needs = {n["sku"]: n for n in (await client.get("/procurement/needs")).json()}
    assert needs["OC90"]["order"]["number"] == draft["number"]
    assert needs["5W30-1L"]["order"] is None


async def test_repeated_and_stale_signals_change_nothing(
    client: AsyncClient, deliver: Deliver, clock: Clock
) -> None:
    order = await order_with(client, [(FILTER, "10", "175.50")])
    await client.post(
        f"/procurement/orders/{order['id']}/receipts",
        json={"lines": [{"line_id": order["lines"][0]["id"], "qty": "10"}]},
    )
    old, new = clock.tick(), clock.tick()
    await deliver("stock.low", low(FILTER, "2.000", "5.000"), new)
    await deliver("stock.low", low(FILTER, "2.000", "5.000"), new)
    await deliver("stock.low", low(FILTER, "4.000", "5.000"), old)

    drafts = (await client.get("/procurement/orders?status=draft")).json()["items"]
    assert [d["lines"] for d in drafts] == [1]
    assert (await client.get("/procurement/needs")).json()[0]["free"] == "2.000"


async def test_need_closes_only_when_stock_is_back_above_minimum(
    client: AsyncClient, deliver: Deliver
) -> None:
    await deliver("stock.low", low(FILTER, "1.000", "4.000"))
    await deliver(
        "stock.received", {"part_id": FILTER, "qty": "2.000", "free": "3.000", "low": True}
    )
    assert (await client.get("/procurement/needs")).json()[0]["free"] == "3.000"
    await deliver(
        "stock.received", {"part_id": FILTER, "qty": "5.000", "free": "8.000", "low": False}
    )
    assert (await client.get("/procurement/needs")).json() == []

    # Новий сигнал відкриває потребу знову; «не замовляти» — закриває.
    await deliver("stock.low", low(FILTER, "3.000", "4.000"))
    assert len((await client.get("/procurement/needs")).json()) == 1
    assert (await client.delete(f"/procurement/needs/{FILTER}")).status_code == 204
    assert (await client.get("/procurement/needs")).json() == []
