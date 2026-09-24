from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from tests.conftest import as_user

OIL = {
    "code": "eng oil",
    "name": "Заміна моторної оливи",
    "category": "Двигун",
    "norm_hours": "0,5",
}
FILTER = {
    "sku": "oc 90",
    "brand": "Mahle",
    "name": "Фільтр оливний",
    "unit": "pcs",
    "price": "245,5",
}


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


# ── Гроші ───────────────────────────────────────────────────────────────────


async def test_money_is_a_two_decimal_string(client: AsyncClient) -> None:
    rate = await client.put("/catalog/labor-rate", json={"amount": "850"})
    assert rate.status_code == 200
    assert rate.json()["amount"] == "850.00"

    part = (await client.post("/catalog/parts", json=FILTER)).json()
    assert part["price"] == "245.50"


async def test_money_rejects_floats_as_text_garbage(client: AsyncClient) -> None:
    for bad in ("12.345", "-5", "abc", "1e3"):
        response = await client.post("/catalog/parts", json={**FILTER, "price": bad})
        assert response.status_code == 422, bad


async def test_zero_labor_rate_is_rejected(client: AsyncClient) -> None:
    assert (await client.put("/catalog/labor-rate", json={"amount": "0"})).status_code == 422


# ── Ставка та ціни робіт ────────────────────────────────────────────────────


async def test_price_is_norm_hours_times_rate(client: AsyncClient) -> None:
    await client.put("/catalog/labor-rate", json={"amount": "850"})
    created = await client.post("/catalog/services", json={**OIL, "norm_hours": "1.35"})

    body = created.json()
    assert body["code"] == "ENGOIL"
    assert body["norm_hours"] == "1.35"
    # 1.35 × 850 = 1147.50 — без float-похибки.
    assert body["price"] == "1147.50"
    assert body["price_source"] == "norm_hours"


async def test_rounding_is_half_up_to_kopiyky(client: AsyncClient) -> None:
    await client.put("/catalog/labor-rate", json={"amount": "333.33"})
    body = (await client.post("/catalog/services", json={**OIL, "norm_hours": "0.15"})).json()
    # 0.15 × 333.33 = 49.9995 → 50.00
    assert body["price"] == "50.00"


async def test_fixed_price_wins_over_rate(client: AsyncClient) -> None:
    await client.put("/catalog/labor-rate", json={"amount": "850"})
    body = (
        await client.post(
            "/catalog/services",
            json={**OIL, "code": "DIAG", "name": "Компʼютерна діагностика", "fixed_price": "600"},
        )
    ).json()
    assert body["price"] == "600.00"
    assert body["price_source"] == "fixed"


async def test_without_rate_price_is_unknown_not_zero(client: AsyncClient) -> None:
    body = (await client.post("/catalog/services", json=OIL)).json()
    assert body["price"] is None
    assert body["price_source"] == "unknown"

    missing = await client.get("/catalog/labor-rate")
    assert missing.status_code == 404


async def test_new_rate_reprices_list_immediately(client: AsyncClient) -> None:
    await client.put("/catalog/labor-rate", json={"amount": "800"})
    await client.post("/catalog/services", json={**OIL, "norm_hours": "1"})
    await client.put("/catalog/labor-rate", json={"amount": "900"})

    page = (await client.get("/catalog/services")).json()
    assert page["labor_rate"] == "900.00"
    assert page["items"][0]["price"] == "900.00"


async def test_rate_history_answers_what_was_in_effect(client: AsyncClient) -> None:
    now = datetime.now(UTC)
    await client.put(
        "/catalog/labor-rate",
        json={"amount": "700", "effective_from": (now - timedelta(days=30)).isoformat()},
    )
    await client.put(
        "/catalog/labor-rate",
        json={"amount": "850", "effective_from": (now - timedelta(days=1)).isoformat()},
    )
    # Запланована на майбутнє ставка ще не діє.
    await client.put(
        "/catalog/labor-rate",
        json={"amount": "950", "effective_from": (now + timedelta(days=7)).isoformat()},
    )

    assert (await client.get("/catalog/labor-rate")).json()["amount"] == "850.00"

    week_ago = (now - timedelta(days=7)).isoformat()
    past = await client.get("/catalog/labor-rate", params={"at": week_ago})
    assert past.json()["amount"] == "700.00"

    history = (await client.get("/catalog/labor-rate/history")).json()
    assert [r["amount"] for r in history] == ["950.00", "850.00", "700.00"]

    too_early = (now - timedelta(days=365)).isoformat()
    assert (await client.get("/catalog/labor-rate", params={"at": too_early})).status_code == 404


# ── Роботи ──────────────────────────────────────────────────────────────────


async def test_duplicate_service_code_is_409(client: AsyncClient) -> None:
    await client.post("/catalog/services", json=OIL)
    response = await client.post(
        "/catalog/services", json={**OIL, "code": "ENG-OIL".replace("-", "")}
    )
    assert response.status_code == 409


async def test_archived_service_frees_its_code(client: AsyncClient) -> None:
    old = (await client.post("/catalog/services", json=OIL)).json()
    await client.post(f"/catalog/services/{old['id']}/archive")

    assert (await client.post("/catalog/services", json=OIL)).status_code == 201
    # Старі наряди посилаються на архівну роботу — вона лишається доступною.
    assert (await client.get(f"/catalog/services/{old['id']}")).status_code == 200


async def test_search_and_category_filter(client: AsyncClient) -> None:
    await client.post("/catalog/services", json=OIL)
    await client.post(
        "/catalog/services",
        json={"code": "ALIGN", "name": "Розвал-сходження", "category": "Ходова", "norm_hours": "1"},
    )

    assert (await client.get("/catalog/services", params={"search": "олив"})).json()["total"] == 1
    by_cat = await client.get("/catalog/services", params={"category": "Ходова"})
    assert [s["code"] for s in by_cat.json()["items"]] == ["ALIGN"]


async def test_clearing_fixed_price_falls_back_to_rate(client: AsyncClient) -> None:
    await client.put("/catalog/labor-rate", json={"amount": "1000"})
    created = (await client.post("/catalog/services", json={**OIL, "fixed_price": "300"})).json()

    response = await client.patch(f"/catalog/services/{created['id']}", json={"fixed_price": None})
    assert response.json()["price"] == "500.00"
    assert response.json()["price_source"] == "norm_hours"


# ── Запчастини ──────────────────────────────────────────────────────────────


async def test_part_sku_and_brand_are_normalized(client: AsyncClient) -> None:
    body = (await client.post("/catalog/parts", json=FILTER)).json()
    assert body["sku"] == "OC90"
    assert body["brand"] == "MAHLE"


async def test_same_sku_different_brand_is_a_different_part(client: AsyncClient) -> None:
    await client.post("/catalog/parts", json=FILTER)
    other = await client.post("/catalog/parts", json={**FILTER, "brand": "Knecht"})
    assert other.status_code == 201

    dup = await client.post("/catalog/parts", json={**FILTER, "sku": "OC90", "brand": "MAHLE"})
    assert dup.status_code == 409
    assert "MAHLE OC90" in dup.json()["detail"]


async def test_part_search_ignores_spaces_in_sku(client: AsyncClient) -> None:
    await client.post("/catalog/parts", json=FILTER)
    assert (await client.get("/catalog/parts", params={"search": "oc 9"})).json()["total"] == 1
    # Регістр кирилиці тут не перевіряється: SQLite знає регістр лише ASCII.
    # На Postgres ILIKE знаходить і «фільтр» — це перевірено окремо.
    assert (await client.get("/catalog/parts", params={"search": "Фільтр"})).json()["total"] == 1


async def test_part_price_update(client: AsyncClient) -> None:
    created = (await client.post("/catalog/parts", json=FILTER)).json()
    response = await client.patch(f"/catalog/parts/{created['id']}", json={"price": "260"})
    assert response.json()["price"] == "260.00"


# ── Права ───────────────────────────────────────────────────────────────────


async def test_mechanic_reads_but_cannot_change_prices(client: AsyncClient) -> None:
    mechanic = as_user("catalog.read,work_orders.read")

    assert (await client.get("/catalog/services", headers=mechanic)).status_code == 200
    denied = await client.put("/catalog/labor-rate", json={"amount": "1"}, headers=mechanic)
    assert denied.status_code == 403
    assert "catalog.write" in denied.json()["detail"]


async def test_part_events_carry_name_and_unit(client: AsyncClient, monkeypatch: Any) -> None:
    """inventory веде картку номенклатури за цими подіями — без запиту назад."""
    from app import events

    sent: list[tuple[str, dict[str, Any]]] = []

    async def capture(event: str, payload: dict[str, Any]) -> None:
        sent.append((event, payload))

    monkeypatch.setattr(events, "publish", capture)
    created = (await client.post("/catalog/parts", json=FILTER)).json()
    await client.patch(f"/catalog/parts/{created['id']}", json={"name": "Фільтр оливи"})

    assert sent[0] == (
        "part.created",
        {
            "id": created["id"],
            "sku": "OC90",
            "brand": "MAHLE",
            "name": "Фільтр оливний",
            "unit": "pcs",
        },
    )
    assert sent[1][0] == "part.updated"
    assert sent[1][1]["name"] == "Фільтр оливи"
