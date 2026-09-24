"""
Gateway — єдина точка входу для фронтенду.

Що робить:
  1. Маршрутизує за першим сегментом: /api/<блок>/… → сервіс блоку, /api зрізається.
  2. Перевіряє токен і передає сервісу, хто прийшов: X-User-Id, X-User-Role,
     X-User-Permissions. Такі ж заголовки з вхідного запиту зрізаються.
  3. Проставляє X-Request-Id, щоб запит можна було простежити по логах сервісів.

Чого не робить: не перевіряє конкретні права — `customers.write` чи ні вирішує
сервіс customers. Gateway відповідає лише на питання «хто це».
"""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.auth import AuthError, JwksCache, bearer_token, verify
from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

# Шляхи без токена. Точний збіг методу й шляху — жодних префіксів, щоб
# випадково не відкрити все під /api/identity/auth/….
PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/identity/auth/login"),
        ("GET", "/identity/.well-known/jwks.json"),
    }
)

# Заголовки одного зʼєднання (RFC 9110 §7.6.1) — далі проксі не йдуть.
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }
)

IDENTITY_HEADERS = ("x-user-id", "x-user-role", "x-user-permissions")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.http = httpx.AsyncClient(timeout=settings.upstream_timeout_seconds)
    app.state.jwks = JwksCache(
        app.state.http, settings.jwks_url, settings.jwks_refresh_cooldown_seconds
    )
    logger.info("Блоки: %s", ", ".join(f"{k}→{v}" for k, v in settings.upstreams.items()))
    yield
    await app.state.http.aclose()


app = FastAPI(
    title="Baymeister — Gateway",
    version="1.0.0",
    description="Єдина точка входу. Публічні інтерфейси блоків описано в contracts/*.yaml.",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _error(status_code: int, detail: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        {"detail": detail}, status_code=status_code, headers={"X-Request-Id": request_id}
    )


@app.get("/health")
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}


METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


@app.api_route("/api/{block}", methods=METHODS)
@app.api_route("/api/{block}/{rest:path}", methods=METHODS)
async def proxy(block: str, request: Request, rest: str = "") -> Response:
    settings = get_settings()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex

    upstream = settings.upstreams.get(block)
    if upstream is None:
        return _error(404, f"Блок {block} не підключений до gateway", request_id)

    # `..` у шляху — або помилка клієнта, або спроба вийти за межі свого блоку.
    if ".." in rest.split("/"):
        return _error(400, "Некоректний шлях", request_id)

    path = f"/{block}/{rest}" if rest else f"/{block}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() not in IDENTITY_HEADERS
    }
    headers["x-request-id"] = request_id
    headers["x-forwarded-for"] = request.client.host if request.client else ""
    headers["x-forwarded-proto"] = request.url.scheme
    headers["x-forwarded-host"] = request.headers.get("host", "")

    if (request.method, path) not in PUBLIC_ROUTES:
        try:
            principal = await verify(
                bearer_token(request.headers.get("authorization")),
                request.app.state.jwks,
                settings.jwt_issuer,
            )
        except AuthError as exc:
            response = _error(401, str(exc), request_id)
            response.headers["WWW-Authenticate"] = "Bearer"
            return response

        headers["x-user-id"] = principal.user_id
        headers["x-user-role"] = principal.role
        headers["x-user-permissions"] = ",".join(principal.permissions)

    client: httpx.AsyncClient = request.app.state.http
    upstream_request = client.build_request(
        request.method,
        # Рядок запиту передається як є, без повторного кодування.
        upstream.rstrip("/") + path + (f"?{request.url.query}" if request.url.query else ""),
        headers=headers,
        content=request.stream(),
    )

    try:
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.TimeoutException:
        logger.warning("[%s] %s %s → тайм-аут %s", request_id, request.method, path, block)
        return _error(504, f"Сервіс {block} не відповів вчасно", request_id)
    except httpx.TransportError as exc:
        logger.warning(
            "[%s] %s %s → %s недоступний: %s", request_id, request.method, path, block, exc
        )
        return _error(502, f"Сервіс {block} недоступний", request_id)

    response_headers = {
        k: v for k, v in upstream_response.headers.items() if k.lower() not in HOP_BY_HOP
    }
    response_headers["x-request-id"] = request_id

    # Тіло передається як є, байт у байт — зокрема стиснене, без розпакування.
    return StreamingResponse(
        upstream_response.aiter_raw(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        background=BackgroundTask(upstream_response.aclose),
    )
