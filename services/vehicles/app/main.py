import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import consumer, events
from app.api.routes import router
from app.config import get_settings
from app.customers_client import CustomersClient

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    http = httpx.AsyncClient()
    app.state.customers = CustomersClient(http, settings.customers_url)

    await events.connect()
    await consumer.start()
    yield
    await consumer.stop()
    await events.disconnect()
    await http.aclose()


app = FastAPI(
    title="Baymeister — Автомобілі",
    version="1.0.0",
    description="Блок vehicles. Публічний інтерфейс описано в contracts/vehicles.yaml.",
    lifespan=lifespan,
)

app.include_router(router)
