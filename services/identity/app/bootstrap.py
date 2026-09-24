"""
Перший власник.

    uv run python -m app.bootstrap

Бере BOOTSTRAP_OWNER_* з оточення і створює власника, тільки якщо в базі ще
немає жодного користувача. Повторний запуск нічого не робить — команду можна
безпечно лишити в скрипті деплою одразу після міграцій.
"""

import asyncio
import logging
import sys

from app import repository
from app.config import get_settings
from app.db import SessionLocal, engine
from app.schemas import UserCreate

logger = logging.getLogger("bootstrap")


async def bootstrap() -> int:
    try:
        return await _bootstrap()
    finally:
        await engine.dispose()


async def _bootstrap() -> int:
    settings = get_settings()

    async with SessionLocal() as session:
        if await repository.count(session) > 0:
            logger.info("Користувачі вже є — нічого не роблю")
            return 0

        if not settings.bootstrap_owner_email or not settings.bootstrap_owner_password:
            logger.error("База порожня, а BOOTSTRAP_OWNER_EMAIL/PASSWORD не задані")
            return 1

        owner = await repository.create(
            session,
            UserCreate(
                email=settings.bootstrap_owner_email,
                name=settings.bootstrap_owner_name,
                role="owner",
                password=settings.bootstrap_owner_password,
            ),
        )
        await session.commit()
        logger.info("Створено власника %s", owner.email)
        return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(asyncio.run(bootstrap()))
