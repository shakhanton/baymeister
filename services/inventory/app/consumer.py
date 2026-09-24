"""
Слухач подій з шини. Логіка — в app/handlers.py; тут лише доставка.

Черга власна й довговічна (`inventory.events`): поки сервіс лежить, резерви
й закриття нарядів накопичуються й доходять після старту. Підтвердження —
після коміту; події, що породив обробник, публікуються теж після коміту.
"""

import json
import logging
from datetime import datetime

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from app import events
from app.config import get_settings
from app.db import SessionLocal
from app.handlers import HANDLERS

logger = logging.getLogger(__name__)

_connection: AbstractRobustConnection | None = None


async def handle(message: AbstractIncomingMessage) -> None:
    try:
        event = json.loads(message.body)
        handler = HANDLERS[event["event"]]
        occurred_at = datetime.fromisoformat(event["occurred_at"])
    except (ValueError, KeyError):
        # Зіпсоване або чуже повідомлення повтором не виправиться — відкидаємо.
        logger.exception("Не вдалося розібрати подію, відкинуто: %r", message.body[:200])
        await message.reject(requeue=False)
        return

    try:
        async with SessionLocal() as session:
            outgoing = await handler(session, event, occurred_at)
            await session.commit()
    except Exception:
        # База недоступна чи інший збій — повідомлення повернеться в чергу.
        logger.exception("Помилка обробки %s, повернуто в чергу", event["event"])
        await message.nack(requeue=True)
        return

    await message.ack()
    for name, payload in outgoing:
        await events.publish(name, payload)


async def start() -> None:
    settings = get_settings()
    if not settings.rabbitmq_url:
        logger.warning("RABBITMQ_URL не заданий — резерви й списання з нарядів не надходитимуть")
        return

    global _connection
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await _connection.channel()
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
