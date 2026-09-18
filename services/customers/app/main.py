import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import events
from app.api.routes import router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await events.connect()
    yield
    await events.disconnect()


app = FastAPI(
    title="Baymeister — Клієнти",
    version="1.0.0",
    description="Блок customers. Публічний інтерфейс описано в contracts/customers.yaml.",
    lifespan=lifespan,
)

app.include_router(router)
