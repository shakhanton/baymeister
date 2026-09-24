from httpx import AsyncClient

from tests.conftest import KOVAL_ID, PETRENKO_ID, FakeCustomers, as_user

GOLF = {
    "customer_id": PETRENKO_ID,
    "plate": "аа 1234 вс",
    "make": "Volkswagen",
    "model": "Golf",
    "vin": "wvwzzz1kzaw123456",
    "year": 2010,
    "mileage_km": 187000,
}


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ── Створення ───────────────────────────────────────────────────────────────


async def test_create_normalizes_plate_and_vin_and_copies_owner(client: AsyncClient) -> None:
    response = await client.post("/vehicles", json=GOLF)

    assert response.status_code == 201
    body = response.json()
    # Кирилиця, пробіли й регістр — той самий номер латиницею.
    assert body["plate"] == "AA1234BC"
    assert body["vin"] == "WVWZZZ1KZAW123456"
    assert body["customer_name"] == "Петренко Іван"
    assert body["customer_phone"] == "+380671234567"
    assert body["mileage_km"] == 187000


async def test_initial_mileage_becomes_first_reading(client: AsyncClient) -> None:
    created = (await client.post("/vehicles", json=GOLF)).json()

    history = (await client.get(f"/vehicles/{created['id']}/mileage")).json()
    assert [r["km"] for r in history] == [187000]


async def test_owner_check_forwards_the_callers_identity(
    client: AsyncClient, customers: FakeCustomers
) -> None:
    await client.post("/vehicles", json=GOLF)

    forwarded = customers.requests[-1].headers
    assert forwarded["x-user-id"] == "00000000-0000-0000-0000-0000000000aa"
    assert "customers.read" in forwarded["x-user-permissions"]


async def test_unknown_customer_is_422(client: AsyncClient) -> None:
    response = await client.post(
        "/vehicles", json={**GOLF, "customer_id": "99999999-9999-9999-9999-999999999999"}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Такого клієнта не існує"


async def test_customers_down_is_503_with_readable_message(
    client: AsyncClient, customers: FakeCustomers
) -> None:
    customers.down = True
    response = await client.post("/vehicles", json=GOLF)

    assert response.status_code == 503
    assert "Клієнти" in response.json()["detail"]


async def test_without_customers_read_owner_cannot_be_chosen(client: AsyncClient) -> None:
    response = await client.post(
        "/vehicles", json=GOLF, headers=as_user("vehicles.read,vehicles.write")
    )
    assert response.status_code == 403


async def test_invalid_vin_is_rejected(client: AsyncClient) -> None:
    # I, O, Q у VIN не вживаються — їх плутають з 1 і 0.
    response = await client.post("/vehicles", json={**GOLF, "vin": "WVWZZZ1KZAW12345O"})
    assert response.status_code == 422


# ── Унікальність ────────────────────────────────────────────────────────────


async def test_duplicate_plate_is_409_even_typed_differently(client: AsyncClient) -> None:
    await client.post("/vehicles", json=GOLF)
    response = await client.post("/vehicles", json={**GOLF, "plate": "AA-1234-BC", "vin": None})

    assert response.status_code == 409
    assert "AA1234BC" in response.json()["detail"]
    assert "Петренко" in response.json()["detail"]


async def test_duplicate_vin_is_409(client: AsyncClient) -> None:
    await client.post("/vehicles", json=GOLF)
    response = await client.post("/vehicles", json={**GOLF, "plate": "KA0001AA"})
    assert response.status_code == 409


async def test_archived_vehicle_frees_its_plate(client: AsyncClient) -> None:
    old = (await client.post("/vehicles", json=GOLF)).json()
    await client.post(f"/vehicles/{old['id']}/archive")

    # Номер перейшов на нове авто — архів цьому не заважає.
    response = await client.post(
        "/vehicles", json={**GOLF, "vin": None, "make": "Skoda", "model": "Octavia"}
    )
    assert response.status_code == 201


# ── Список і пошук ──────────────────────────────────────────────────────────


async def test_search_and_filter_by_customer(client: AsyncClient) -> None:
    await client.post("/vehicles", json=GOLF)
    await client.post(
        "/vehicles",
        json={"customer_id": KOVAL_ID, "plate": "BC5555KA", "make": "Toyota", "model": "Corolla"},
    )

    assert (await client.get("/vehicles", params={"search": "1234"})).json()["total"] == 1
    assert (await client.get("/vehicles", params={"search": "Коваль"})).json()["total"] == 1
    assert (await client.get("/vehicles", params={"search": "golf"})).json()["total"] == 1

    mine = await client.get("/vehicles", params={"customer_id": KOVAL_ID})
    assert [v["make"] for v in mine.json()["items"]] == ["Toyota"]


async def test_archived_vehicle_leaves_list_but_stays_reachable(client: AsyncClient) -> None:
    created = (await client.post("/vehicles", json=GOLF)).json()
    await client.post(f"/vehicles/{created['id']}/archive")

    assert (await client.get("/vehicles")).json()["total"] == 0
    assert (await client.get("/vehicles", params={"archived": True})).json()["total"] == 1
    # Наряди посилаються на автомобіль — він мусить лишитись доступним.
    assert (await client.get(f"/vehicles/{created['id']}")).status_code == 200


# ── Оновлення і продаж ──────────────────────────────────────────────────────


async def test_sale_to_another_customer_refreshes_owner_copy(client: AsyncClient) -> None:
    created = (await client.post("/vehicles", json=GOLF)).json()

    response = await client.patch(f"/vehicles/{created['id']}", json={"customer_id": KOVAL_ID})

    assert response.status_code == 200
    assert response.json()["customer_name"] == "Коваль Олена"
    assert response.json()["plate"] == "AA1234BC"


async def test_partial_update_does_not_touch_customers(
    client: AsyncClient, customers: FakeCustomers
) -> None:
    created = (await client.post("/vehicles", json=GOLF)).json()
    calls = len(customers.requests)

    response = await client.patch(f"/vehicles/{created['id']}", json={"color": "сірий"})

    assert response.json()["color"] == "сірий"
    assert len(customers.requests) == calls


async def test_changing_plate_to_a_taken_one_is_409(client: AsyncClient) -> None:
    await client.post("/vehicles", json=GOLF)
    other = (
        await client.post(
            "/vehicles",
            json={
                "customer_id": KOVAL_ID,
                "plate": "BC5555KA",
                "make": "Toyota",
                "model": "Corolla",
            },
        )
    ).json()

    response = await client.patch(f"/vehicles/{other['id']}", json={"plate": "AA1234BC"})
    assert response.status_code == 409


# ── Пробіг ──────────────────────────────────────────────────────────────────


async def test_mileage_cannot_go_back(client: AsyncClient) -> None:
    created = (await client.post("/vehicles", json=GOLF)).json()

    forward = await client.post(f"/vehicles/{created['id']}/mileage", json={"km": 190500})
    assert forward.status_code == 201

    back = await client.post(f"/vehicles/{created['id']}/mileage", json={"km": 150000})
    assert back.status_code == 409
    assert "190500" in back.json()["detail"]

    vehicle = (await client.get(f"/vehicles/{created['id']}")).json()
    assert vehicle["mileage_km"] == 190500


async def test_mileage_history_newest_first(client: AsyncClient) -> None:
    created = (await client.post("/vehicles", json=GOLF)).json()
    await client.post(f"/vehicles/{created['id']}/mileage", json={"km": 190000, "note": "ТО"})

    history = (await client.get(f"/vehicles/{created['id']}/mileage")).json()
    assert [r["km"] for r in history] == [190000, 187000]
    assert history[0]["note"] == "ТО"


# ── Права ───────────────────────────────────────────────────────────────────


async def test_permissions(client: AsyncClient) -> None:
    created = (await client.post("/vehicles", json=GOLF)).json()
    mechanic = as_user("vehicles.read,customers.read")

    assert (await client.get("/vehicles", headers=mechanic)).status_code == 200
    denied = await client.post(
        f"/vehicles/{created['id']}/mileage", json={"km": 200000}, headers=mechanic
    )
    assert denied.status_code == 403
    assert "vehicles.write" in denied.json()["detail"]

    anonymous = {"X-User-Id": "", "X-User-Role": "", "X-User-Permissions": ""}
    assert (await client.get("/vehicles", headers=anonymous)).status_code == 401
