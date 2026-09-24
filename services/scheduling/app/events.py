"""
Публікація доменних подій.

`notifications` нагадує клієнту про запис за `appointment.booked` і
`appointment.rescheduled`; `analytics` рахує завантаження постів і частку
неявок за `appointment.no_show`.

Якщо RABBITMQ_URL не заданий, події пишуться в лог. Це дозволяє підняти блок і
працювати з ним без брокера.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import aio_pika

from app.config import get_settings

logger = logging.getLogger(__name__)

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect() -> None:
    settings = get_settings()
    if not settings.rabbitmq_url:
        logger.warning("RABBITMQ_URL не заданий — події йдуть у лог, не в шину")
        return

    global _connection, _exchange
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await _connection.channel()
    _exchange = await channel.declare_exchange(
        settings.events_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )
    logger.info("Підключено до шини подій")


async def disconnect() -> None:
    if _connection is not None:
        await _connection.close()


async def publish(event: str, payload: dict[str, Any]) -> None:
    """
    Слухачі мусять обробляти повторну доставку ідемпотентно — брокер гарантує
    at-least-once, а не exactly-once.
    """
    body = {
        "event": event,
        "occurred_at": datetime.now(UTC).isoformat(),
        "producer": "scheduling",
        "payload": payload,
    }

    if _exchange is None:
        logger.info("подія (без шини): %s", json.dumps(body, ensure_ascii=False, default=str))
        return

    await _exchange.publish(
        aio_pika.Message(
            body=json.dumps(body, ensure_ascii=False, default=str).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=event,
    )
