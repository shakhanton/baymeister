import jwt
from httpx import AsyncClient
from jwt import PyJWK

from app.models import User
from tests.conftest import OWNER_PASSWORD, as_user

MECHANIC = {
    "email": "Oleh@Example.com",
    "name": "Коваленко Олег",
    "role": "mechanic",
    "password": "mechanic-password",
}


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ── Вхід і токен ────────────────────────────────────────────────────────────


async def test_login_returns_token_verifiable_by_jwks(client: AsyncClient, owner: User) -> None:
    response = await client.post(
        "/identity/auth/login",
        json={"email": "OWNER@example.com", "password": OWNER_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "owner"
    assert body["user"]["permissions"] == ["*"]

    # Так само перевіряє gateway: ключ за kid з JWKS.
    keys = (await client.get("/identity/.well-known/jwks.json")).json()["keys"]
    header = jwt.get_unverified_header(body["access_token"])
    key = next(k for k in keys if k["kid"] == header["kid"])
    claims = jwt.decode(
        body["access_token"],
        PyJWK(key).key,
        algorithms=["RS256"],
        issuer="baymeister-identity",
    )
    assert claims["sub"] == str(owner.id)
    assert claims["perms"] == ["*"]


async def test_wrong_password_and_unknown_email_look_the_same(
    client: AsyncClient, owner: User
) -> None:
    wrong = await client.post(
        "/identity/auth/login",
        json={"email": owner.email, "password": "not-the-password"},
    )
    unknown = await client.post(
        "/identity/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_deactivated_user_cannot_log_in(
    client: AsyncClient, as_owner: dict[str, str]
) -> None:
    created = (await client.post("/identity/users", json=MECHANIC, headers=as_owner)).json()
    await client.post(f"/identity/users/{created['id']}/deactivate", headers=as_owner)

    response = await client.post(
        "/identity/auth/login",
        json={"email": MECHANIC["email"], "password": MECHANIC["password"]},
    )
    assert response.status_code == 401


async def test_me_requires_gateway_headers(client: AsyncClient, owner: User) -> None:
    anonymous = await client.get("/identity/me")
    assert anonymous.status_code == 401

    me = await client.get("/identity/me", headers=as_user(owner, "*"))
    assert me.status_code == 200
    assert me.json()["email"] == owner.email


# ── Права ───────────────────────────────────────────────────────────────────


async def test_users_endpoints_check_permissions(client: AsyncClient, owner: User) -> None:
    reader = as_user(owner, "identity.read")

    assert (await client.get("/identity/users", headers=reader)).status_code == 200

    forbidden = await client.post("/identity/users", json=MECHANIC, headers=reader)
    assert forbidden.status_code == 403
    assert "identity.write" in forbidden.json()["detail"]

    nobody = as_user(owner, "customers.read")
    assert (await client.get("/identity/roles", headers=nobody)).status_code == 403


async def test_roles_catalog(client: AsyncClient, as_owner: dict[str, str]) -> None:
    roles = (await client.get("/identity/roles", headers=as_owner)).json()
    by_id = {r["id"]: r for r in roles}

    assert by_id["owner"]["permissions"] == ["*"]
    assert "inspections.write" in by_id["mechanic"]["permissions"]
    assert "finance.write" not in by_id["mechanic"]["permissions"]


# ── Співробітники ───────────────────────────────────────────────────────────


async def test_create_user_lowercases_email_and_hides_password(
    client: AsyncClient, as_owner: dict[str, str]
) -> None:
    response = await client.post("/identity/users", json=MECHANIC, headers=as_owner)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "oleh@example.com"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body


async def test_duplicate_email_is_rejected(client: AsyncClient, as_owner: dict[str, str]) -> None:
    await client.post("/identity/users", json=MECHANIC, headers=as_owner)
    response = await client.post(
        "/identity/users",
        json={**MECHANIC, "email": "oleh@example.com", "name": "Інша людина"},
        headers=as_owner,
    )
    assert response.status_code == 409


async def test_short_password_is_rejected(client: AsyncClient, as_owner: dict[str, str]) -> None:
    response = await client.post(
        "/identity/users", json={**MECHANIC, "password": "short"}, headers=as_owner
    )
    assert response.status_code == 422


async def test_password_change_takes_effect(client: AsyncClient, as_owner: dict[str, str]) -> None:
    created = (await client.post("/identity/users", json=MECHANIC, headers=as_owner)).json()
    await client.patch(
        f"/identity/users/{created['id']}",
        json={"password": "brand-new-password"},
        headers=as_owner,
    )

    old = await client.post(
        "/identity/auth/login",
        json={"email": MECHANIC["email"], "password": MECHANIC["password"]},
    )
    new = await client.post(
        "/identity/auth/login",
        json={"email": MECHANIC["email"], "password": "brand-new-password"},
    )
    assert old.status_code == 401
    assert new.status_code == 200


async def test_search_and_inactive_filter(client: AsyncClient, as_owner: dict[str, str]) -> None:
    created = (await client.post("/identity/users", json=MECHANIC, headers=as_owner)).json()

    found = await client.get("/identity/users", params={"search": "Коваленко"}, headers=as_owner)
    assert found.json()["total"] == 1

    await client.post(f"/identity/users/{created['id']}/deactivate", headers=as_owner)

    active = await client.get("/identity/users", headers=as_owner)
    assert [u["email"] for u in active.json()["items"]] == ["owner@example.com"]

    inactive = await client.get("/identity/users", params={"inactive": True}, headers=as_owner)
    assert inactive.json()["total"] == 1

    # Наряди й табель посилаються на співробітника — він лишається доступним.
    direct = await client.get(f"/identity/users/{created['id']}", headers=as_owner)
    assert direct.status_code == 200
    assert direct.json()["is_active"] is False


# ── Захист від втрати доступу ───────────────────────────────────────────────


async def test_cannot_deactivate_yourself(
    client: AsyncClient, owner: User, as_owner: dict[str, str]
) -> None:
    response = await client.post(f"/identity/users/{owner.id}/deactivate", headers=as_owner)
    assert response.status_code == 409


async def test_last_owner_cannot_be_demoted_or_deactivated(
    client: AsyncClient, owner: User
) -> None:
    other = await client.post(
        "/identity/users",
        json={**MECHANIC, "role": "manager"},
        headers=as_user(owner, "*"),
    )
    manager = as_user(owner, "identity.write")
    manager["X-User-Id"] = other.json()["id"]

    demote = await client.patch(
        f"/identity/users/{owner.id}", json={"role": "manager"}, headers=manager
    )
    assert demote.status_code == 409

    deactivate = await client.post(f"/identity/users/{owner.id}/deactivate", headers=manager)
    assert deactivate.status_code == 409


async def test_owner_can_be_demoted_once_another_owner_exists(
    client: AsyncClient, owner: User, as_owner: dict[str, str]
) -> None:
    await client.post("/identity/users", json={**MECHANIC, "role": "owner"}, headers=as_owner)

    response = await client.patch(
        f"/identity/users/{owner.id}", json={"role": "manager"}, headers=as_owner
    )
    assert response.status_code == 200
    assert response.json()["role"] == "manager"
