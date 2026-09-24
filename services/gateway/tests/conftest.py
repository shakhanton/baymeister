import json
import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

# Має бути раніше за імпорт app.*, бо налаштування кешуються.
os.environ["UPSTREAMS"] = '{"identity": "http://identity", "customers": "http://customers"}'
os.environ["JWKS_URL"] = "http://identity/identity/.well-known/jwks.json"

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.auth import JwksCache
from app.main import app

KID = "test-key"


class _Stream(httpx.AsyncByteStream):
    """Тіло, яке ще не прочитане, — як у справжньої мережевої відповіді.

    httpx.Response(json=...) вичитує тіло одразу, а gateway стрімить його далі.
    """

    def __init__(self, body: bytes) -> None:
        self._body = body

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self._body


@dataclass
class Upstreams:
    """Підмінені сервіси: JWKS від identity і «луна» для решти запитів."""

    private_pem: bytes
    public_jwk: dict[str, Any]
    requests: list[httpx.Request] = field(default_factory=list)
    jwks_calls: int = 0
    down: bool = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/identity/.well-known/jwks.json":
            self.jwks_calls += 1
            body = json.dumps({"keys": [self.public_jwk]}).encode()
            return httpx.Response(200, stream=_Stream(body))

        if self.down:
            raise httpx.ConnectError("connection refused", request=request)

        self.requests.append(request)
        return httpx.Response(
            200,
            stream=_Stream(b'{"ok": true}'),
            headers={"Content-Type": "application/json", "X-Upstream": request.url.host},
        )

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


def _keypair() -> tuple[bytes, dict[str, Any]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    jwk = RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return pem, jwk


@pytest.fixture(scope="session")
def keypair() -> tuple[bytes, dict[str, Any]]:
    return _keypair()


@pytest.fixture
def upstreams(keypair: tuple[bytes, dict[str, Any]]) -> Upstreams:
    return Upstreams(private_pem=keypair[0], public_jwk=keypair[1])


@pytest.fixture
def make_token(upstreams: Upstreams) -> Callable[..., str]:
    def make(
        *,
        sub: str = "7b1f0c1e-0000-0000-0000-000000000001",
        perms: list[str] | None = None,
        expires_in: int = 3600,
        issuer: str = "baymeister-identity",
        kid: str = KID,
        key: bytes | None = None,
    ) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "iss": issuer,
                "sub": sub,
                "role": "manager",
                "perms": perms if perms is not None else ["customers.read"],
                "iat": now,
                "exp": now + timedelta(seconds=expires_in),
            },
            key or upstreams.private_pem,
            algorithm="RS256",
            headers={"kid": kid},
        )

    return make


@pytest.fixture
async def client(upstreams: Upstreams) -> AsyncIterator[httpx.AsyncClient]:
    # ASGITransport не запускає lifespan — стан, який він створює, ставимо тут.
    http = httpx.AsyncClient(transport=httpx.MockTransport(upstreams.handler))
    app.state.http = http
    app.state.jwks = JwksCache(http, os.environ["JWKS_URL"], cooldown=30.0)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as c:
        yield c
    await http.aclose()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
