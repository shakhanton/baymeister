"""
Слухач подій з шини — за зразком vehicles.

Список нарядів показує імʼя, телефон і держномер без запитів до сусідів: це
копії, які оновлюються за `customer.updated` і `vehicle.updated`. Черга власна
й довговічна, підтвердження — після коміту, обробники ідемпотентні.
"""

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from app import repository
from app.config import get_settings
from app.db import SessionLocal
from app.peers import vehicle_label

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]

_connection: AbstractRobustConnection | None = None


async def on_customer_updated(event: dict[str, Any]) -> None:
    payload = event["payload"]
    async with SessionLocal() as session:
        changed = await repository.apply_customer_update(
            session,
            customer_id=uuid.UUID(payload["id"]),
            name=payload["name"],
            phone=payload["phone"],
            occurred_at=datetime.fromisoformat(event["occurred_at"]),
        )
        await session.commit()
    logger.info("customer.updated %s → оновлено нарядів: %d", payload["id"], changed)


async def on_vehicle_updated(event: dict[str, Any]) -> None:
    payload = event["payload"]
    async with SessionLocal() as session:
        changed = await repository.apply_vehicle_update(
            session,
            vehicle_id=uuid.UUID(payload["id"]),
            label=vehicle_label(payload["plate"], payload["make"], payload["model"]),
            occurred_at=datetime.fromisoformat(event["occurred_at"]),
        )
        await session.commit()
    logger.info("vehicle.updated %s → оновлено нарядів: %d", payload["id"], changed)


HANDLERS: dict[str, Handler] = {
    "customer.updated": on_customer_updated,
    "vehicle.updated": on_vehicle_updated,
}


async def handle(message: AbstractIncomingMessage) -> None:
    try:
        event = json.loads(message.body)
        handler = HANDLERS[event["event"]]
    except (ValueError, KeyError):
        # Зіпсоване або чуже повідомлення повтором не виправиться — відкидаємо.
        logger.exception("Не вдалося розібрати подію, відкинуто: %r", message.body[:200])
        await message.reject(requeue=False)
        return

    try:
        await handler(event)
    except Exception:
        # База недоступна чи інший збій — повідомлення повернеться в чергу.
        logger.exception("Помилка обробки %s, повернуто в чергу", event["event"])
        await message.nack(requeue=True)
        return

    await message.ack()


async def start() -> None:
    settings = get_settings()
    if not settings.rabbitmq_url:
        logger.warning(
            "RABBITMQ_URL не заданий — копії клієнтів і авто не оновлюватимуться подіями"
        )
        return

    global _connection
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await _connection.channel()
    # Не брати наступне повідомлення, поки не оброблене попереднє.
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        settings.events_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(settings.events_queue, durable=True)
    for routing_key in HANDLERS:
        await queue.bind(exchange, routing_key=routing_key)

    await queue.consume(handle)
    logger.info("Слухаю події: %s", ", ".join(HANDLERS))


async def stop() -> None:
    if _connection is not None:
        await _connection.close()
