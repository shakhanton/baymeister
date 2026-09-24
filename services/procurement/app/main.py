import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import consumer, events
from app.api.routes import router
from app.catalog_client import CatalogClient
from app.config import get_settings

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    http = httpx.AsyncClient()
    app.state.catalog = CatalogClient(http, settings.catalog_url)

    await events.connect()
    await consumer.start()
    yield
    await consumer.stop()
    await events.disconnect()
    await http.aclose()


app = FastAPI(
    title="Baymeister — Закупівлі",
    version="1.0.0",
    description="Блок procurement. Публічний інтерфейс описано в contracts/procurement.yaml.",
    lifespan=lifespan,
)

app.include_router(router)
