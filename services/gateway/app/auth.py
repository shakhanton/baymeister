"""
Перевірка токена.

Токен підписує identity приватним ключем, gateway перевіряє публічним з JWKS.
Ключі кешуються; невідомий `kid` означає ротацію — JWKS перечитується, але не
частіше за cooldown.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import PyJWK

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Токен відсутній, зіпсований, прострочений або підписаний невідомим ключем."""


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    permissions: list[str]


class JwksCache:
    def __init__(self, client: httpx.AsyncClient, url: str, cooldown: float) -> None:
        self._client = client
        self._url = url
        self._cooldown = cooldown
        self._keys: dict[str, Any] = {}
        self._fetched_at = float("-inf")
        self._lock = asyncio.Lock()

    async def get(self, kid: str) -> Any:
        if kid in self._keys:
            return self._keys[kid]

        async with self._lock:
            # Поки чекали на замок, інший запит міг уже перечитати ключі.
            if kid not in self._keys and time.monotonic() - self._fetched_at >= self._cooldown:
                await self._refresh()

        if kid not in self._keys:
            raise AuthError("Токен підписаний невідомим ключем")
        return self._keys[kid]

    async def _refresh(self) -> None:
        self._fetched_at = time.monotonic()
        try:
            response = await self._client.get(self._url, timeout=5.0)
            response.raise_for_status()
            keys = response.json()["keys"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            # Старі ключі лишаються: identity впав — ті, хто вже увійшов, працюють далі.
            logger.warning("Не вдалося прочитати JWKS з %s: %s", self._url, exc)
            return

        self._keys = {k["kid"]: PyJWK(k).key for k in keys if k.get("alg") == "RS256"}
        logger.info("JWKS оновлено, ключів: %d", len(self._keys))


def bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthError("Потрібно увійти")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthError("Очікується заголовок Authorization: Bearer <токен>")
    return token.strip()


async def verify(token: str, jwks: JwksCache, issuer: str) -> Principal:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthError("Недійсний токен") from exc

    kid = header.get("kid")
    if not isinstance(kid, str):
        raise AuthError("Недійсний токен")

    key = await jwks.get(kid)
    try:
        claims = jwt.decode(
            token,
            key,
            # Алгоритм фіксований: інакше токен з alg=none або HS256 з публічним
            # ключем як секретом пройшов би перевірку.
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Сесія завершилась, увійдіть знову") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Недійсний токен") from exc

    perms = claims.get("perms", [])
    if not isinstance(perms, list) or not all(isinstance(p, str) for p in perms):
        raise AuthError("Недійсний токен")

    return Principal(
        user_id=str(claims["sub"]), role=str(claims.get("role", "")), permissions=perms
    )
