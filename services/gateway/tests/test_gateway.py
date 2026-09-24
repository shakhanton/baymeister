from collections.abc import Callable

from httpx import AsyncClient

from tests.conftest import Upstreams, _keypair, bearer


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ── Маршрутизація ───────────────────────────────────────────────────────────


async def test_routes_by_first_segment_and_strips_api(
    client: AsyncClient, upstreams: Upstreams, make_token: Callable[..., str]
) -> None:
    response = await client.get(
        "/api/customers/42", params={"search": "Петренко"}, headers=bearer(make_token())
    )

    assert response.status_code == 200
    assert response.headers["x-upstream"] == "customers"
    assert upstreams.last.url.path == "/customers/42"
    assert upstreams.last.url.params["search"] == "Петренко"


async def test_bare_block_path_is_routed(
    client: AsyncClient, upstreams: Upstreams, make_token: Callable[..., str]
) -> None:
    response = await client.get("/api/customers", headers=bearer(make_token()))
    assert response.status_code == 200
    assert upstreams.last.url.path == "/customers"


async def test_unknown_block_is_404(client: AsyncClient, make_token: Callable[..., str]) -> None:
    response = await client.get("/api/payroll/runs", headers=bearer(make_token()))
    assert response.status_code == 404
    assert "payroll" in response.json()["detail"]


async def test_dot_dot_in_path_is_rejected(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    # httpx нормалізує `..` сам, тому шлях подаємо закодованим так, щоб він дожив до gateway.
    response = await client.get(
        "/api/identity/auth/login/%2E%2E/%2E%2E/users", headers=bearer(make_token())
    )
    assert response.status_code in (400, 404)


async def test_request_body_and_method_are_forwarded(
    client: AsyncClient, upstreams: Upstreams, make_token: Callable[..., str]
) -> None:
    await client.patch(
        "/api/customers/42", json={"name": "Нове імʼя"}, headers=bearer(make_token())
    )
    assert upstreams.last.method == "PATCH"
    assert "Нове імʼя" in upstreams.last.content.decode()


# ── Автентифікація ──────────────────────────────────────────────────────────


async def test_missing_token_is_401(client: AsyncClient, upstreams: Upstreams) -> None:
    response = await client.get("/api/customers")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert upstreams.requests == []


async def test_login_and_jwks_are_public(client: AsyncClient, upstreams: Upstreams) -> None:
    login = await client.post("/api/identity/auth/login", json={"email": "a@b.c", "password": "x"})
    assert login.status_code == 200
    assert "x-user-id" not in upstreams.last.headers

    jwks = await client.get("/api/identity/.well-known/jwks.json")
    assert jwks.status_code == 200


async def test_other_identity_routes_need_a_token(client: AsyncClient) -> None:
    assert (await client.get("/api/identity/users")).status_code == 401
    # Метод теж має значення: публічний лише POST на login.
    assert (await client.get("/api/identity/auth/login")).status_code == 401


async def test_verified_identity_is_forwarded_as_headers(
    client: AsyncClient, upstreams: Upstreams, make_token: Callable[..., str]
) -> None:
    token = make_token(sub="user-1", perms=["customers.read", "customers.write"])
    await client.get("/api/customers", headers=bearer(token))

    headers = upstreams.last.headers
    assert headers["x-user-id"] == "user-1"
    assert headers["x-user-role"] == "manager"
    assert headers["x-user-permissions"] == "customers.read,customers.write"
    assert headers["x-request-id"]


async def test_spoofed_identity_headers_are_stripped(
    client: AsyncClient, upstreams: Upstreams, make_token: Callable[..., str]
) -> None:
    await client.get(
        "/api/customers",
        headers={**bearer(make_token(sub="real")), "X-User-Id": "admin", "X-User-Permissions": "*"},
    )
    assert upstreams.last.headers["x-user-id"] == "real"
    assert upstreams.last.headers["x-user-permissions"] == "customers.read"

    # На публічному маршруті токена немає — підроблені заголовки теж не проходять.
    await client.post(
        "/api/identity/auth/login",
        json={},
        headers={"X-User-Id": "admin", "X-User-Permissions": "*"},
    )
    assert "x-user-id" not in upstreams.last.headers
    assert "x-user-permissions" not in upstreams.last.headers


async def test_expired_token_is_401(client: AsyncClient, make_token: Callable[..., str]) -> None:
    response = await client.get("/api/customers", headers=bearer(make_token(expires_in=-10)))
    assert response.status_code == 401
    assert "увійдіть знову" in response.json()["detail"]


async def test_token_from_foreign_key_is_401(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    foreign_pem, _ = _keypair()
    response = await client.get("/api/customers", headers=bearer(make_token(key=foreign_pem)))
    assert response.status_code == 401


async def test_wrong_issuer_is_401(client: AsyncClient, make_token: Callable[..., str]) -> None:
    response = await client.get("/api/customers", headers=bearer(make_token(issuer="someone-else")))
    assert response.status_code == 401


async def test_garbage_token_is_401(client: AsyncClient) -> None:
    response = await client.get("/api/customers", headers=bearer("not.a.jwt"))
    assert response.status_code == 401


async def test_unknown_kid_refetches_jwks_at_most_once_per_cooldown(
    client: AsyncClient, upstreams: Upstreams, make_token: Callable[..., str]
) -> None:
    await client.get("/api/customers", headers=bearer(make_token()))
    assert upstreams.jwks_calls == 1

    for _ in range(5):
        response = await client.get("/api/customers", headers=bearer(make_token(kid="rotated")))
        assert response.status_code == 401

    assert upstreams.jwks_calls == 1


# ── Відмови ─────────────────────────────────────────────────────────────────


async def test_upstream_down_is_502(
    client: AsyncClient, upstreams: Upstreams, make_token: Callable[..., str]
) -> None:
    token = make_token()
    await client.get("/api/customers", headers=bearer(token))  # прогріти JWKS
    upstreams.down = True

    response = await client.get("/api/customers", headers=bearer(token))
    assert response.status_code == 502
    assert "customers" in response.json()["detail"]
    assert response.headers["x-request-id"]
