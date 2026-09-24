"""
Паролі й токени.

Токен підписується приватним RSA-ключем (RS256). Gateway перевіряє його за
публічним ключем з /identity/.well-known/jwks.json — спільного секрету між
сервісами немає, і скомпрометований gateway не може випускати токени.
"""

import base64
import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings

logger = logging.getLogger(__name__)

_hasher = PasswordHasher()

# Хеш випадкового пароля. Перевіряється, коли email не знайдено, — щоб час
# відповіді не видавав, чи існує такий користувач.
_DUMMY_HASH = _hasher.hash(uuid.uuid4().hex)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


@dataclass(frozen=True)
class SigningKey:
    kid: str
    private_pem: bytes
    public: rsa.RSAPublicKey


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@lru_cache
def get_signing_key() -> SigningKey:
    settings = get_settings()

    pem: bytes | None = None
    if settings.jwt_private_key:
        pem = settings.jwt_private_key.encode()
    elif settings.jwt_private_key_file:
        pem = Path(settings.jwt_private_key_file).read_bytes()

    if pem is None:
        logger.warning(
            "JWT_PRIVATE_KEY не заданий — згенеровано тимчасовий ключ. "
            "Після перезапуску всі видані токени стануть недійсними."
        )
        generated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = generated.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    private = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(private, rsa.RSAPrivateKey):
        raise ValueError("JWT_PRIVATE_KEY має бути RSA-ключем")

    public = private.public_key()
    der = public.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    kid = hashlib.sha256(der).hexdigest()[:16]
    return SigningKey(kid=kid, private_pem=pem, public=public)


def jwks() -> dict[str, list[dict[str, str]]]:
    key = get_signing_key()
    numbers = key.public.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": key.kid,
                "use": "sig",
                "alg": "RS256",
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }


def issue_token(*, user_id: uuid.UUID, name: str, role: str, permissions: list[str]) -> str:
    """
    У токені лежить усе, що потрібно gateway для заголовків X-User-*, — щоб
    на кожен запит не ходити в identity. Ціна: зміна ролі діє з наступного входу.
    """
    settings = get_settings()
    key = get_signing_key()
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "sub": str(user_id),
        "name": name,
        "role": role,
        "perms": permissions,
        "iat": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
    }
    return jwt.encode(claims, key.private_pem, algorithm="RS256", headers={"kid": key.kid})
