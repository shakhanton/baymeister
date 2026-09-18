from httpx import AsyncClient

PETRENKO = {
    "type": "individual",
    "name": "Петренко Іван Миколайович",
    "phone": "+380671234567",
}


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_returns_201_with_generated_fields(client: AsyncClient) -> None:
    response = await client.post("/customers", json=PETRENKO)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == PETRENKO["name"]
    assert body["discount_percent"] == 0
    assert body["archived_at"] is None
    assert body["id"]


async def test_duplicate_phone_is_rejected(client: AsyncClient) -> None:
    await client.post("/customers", json=PETRENKO)
    response = await client.post("/customers", json={**PETRENKO, "name": "Інша людина"})

    assert response.status_code == 409
    assert PETRENKO["phone"] in response.json()["detail"]


async def test_phone_must_be_e164(client: AsyncClient) -> None:
    response = await client.post("/customers", json={**PETRENKO, "phone": "067 123 45 67"})
    assert response.status_code == 422


async def test_get_missing_customer_is_404(client: AsyncClient) -> None:
    response = await client.get("/customers/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_search_matches_name_and_phone(client: AsyncClient) -> None:
    await client.post("/customers", json=PETRENKO)
    await client.post(
        "/customers",
        json={"type": "company", "name": "ТОВ Автотранс", "phone": "+380509876543"},
    )

    by_name = await client.get("/customers", params={"search": "Автотранс"})
    assert by_name.json()["total"] == 1

    by_phone = await client.get("/customers", params={"search": "067123"})
    assert by_phone.json()["total"] == 1

    everything = await client.get("/customers")
    assert everything.json()["total"] == 2


async def test_filter_by_type(client: AsyncClient) -> None:
    await client.post("/customers", json=PETRENKO)
    await client.post(
        "/customers",
        json={"type": "company", "name": "ТОВ Автотранс", "phone": "+380509876543"},
    )

    response = await client.get("/customers", params={"type": "company"})
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "ТОВ Автотранс"


async def test_partial_update_leaves_other_fields_alone(client: AsyncClient) -> None:
    created = (await client.post("/customers", json=PETRENKO)).json()

    response = await client.patch(
        f"/customers/{created['id']}", json={"discount_percent": 12.5}
    )

    assert response.status_code == 200
    assert response.json()["discount_percent"] == 12.5
    assert response.json()["name"] == PETRENKO["name"]


async def test_update_to_taken_phone_is_rejected(client: AsyncClient) -> None:
    await client.post("/customers", json=PETRENKO)
    other = (
        await client.post(
            "/customers",
            json={"type": "company", "name": "ТОВ Автотранс", "phone": "+380509876543"},
        )
    ).json()

    response = await client.patch(f"/customers/{other['id']}", json={"phone": PETRENKO["phone"]})
    assert response.status_code == 409


async def test_archived_customer_leaves_the_list_but_stays_reachable(
    client: AsyncClient,
) -> None:
    created = (await client.post("/customers", json=PETRENKO)).json()

    archived = await client.post(f"/customers/{created['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None

    active = await client.get("/customers")
    assert active.json()["total"] == 0

    in_archive = await client.get("/customers", params={"archived": True})
    assert in_archive.json()["total"] == 1

    # Наряди й автомобілі посилаються на клієнта — він мусить лишитись доступним.
    direct = await client.get(f"/customers/{created['id']}")
    assert direct.status_code == 200


async def test_pagination_reports_total_beyond_the_page(client: AsyncClient) -> None:
    for i in range(5):
        await client.post(
            "/customers",
            json={"type": "individual", "name": f"Клієнт {i}", "phone": f"+38067000000{i}"},
        )

    response = await client.get("/customers", params={"limit": 2, "offset": 2})
    body = response.json()

    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["offset"] == 2
