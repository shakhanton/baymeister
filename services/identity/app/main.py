import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import events
from app.api.routes import router
from app.security import get_signing_key

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Ключ вантажиться при старті: зламаний PEM має валити деплой, а не перший вхід.
    get_signing_key()
    await events.connect()
    yield
    await events.disconnect()


app = FastAPI(
    title="Baymeister — Користувачі та ролі",
    version="1.0.0",
    description="Блок identity. Публічний інтерфейс описано в contracts/identity.yaml.",
    lifespan=lifespan,
)

app.include_router(router)
