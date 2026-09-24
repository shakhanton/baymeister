# Блок `work-orders`

Наряд-замовлення — ядро системи: клієнт, авто, роботи й запчастини з цінами на
момент додавання, суми, статуси.

Публічний інтерфейс — [`contracts/work-orders.yaml`](../../contracts/work-orders.yaml).
Опис блоку — [`docs/work-orders.md`](../../docs/work-orders.md).

## Запуск

```bash
docker compose up -d postgres rabbitmq   # з кореня репозиторію
cd services/work-orders
cp .env.example .env
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8006
```

Документація API — http://localhost:8006/docs

## Перевірки

```bash
uv run pytest        # 19 тестів, SQLite у пам'яті, сусіди й шина підмінені
uv run ruff check .
uv run mypy app
```

## Структура

```
app/config.py      налаштування з оточення, зокрема BUSINESS_TIMEZONE
app/db.py          сесія SQLAlchemy, власна схема
app/models.py      orders, order_lines, order_counters; UtcDateTime
app/money.py       гроші й кількість: Decimal усередині, рядок назовні
app/pricing.py     суми наряду з рядків — одне місце для всієї арифметики
app/schemas.py     Pydantic — вони ж джерело OpenAPI
app/repository.py  запити до бази; номер наряду; оновлення копій
app/peers.py       синхронне читання з customers, vehicles, catalog
app/consumer.py    слухач customer.updated і vehicle.updated
app/events.py      публікація подій у шину
app/api/auth.py    хто робить запит і чи має право — з заголовків X-User-*
app/api/routes.py  ендпоінти, без SQL; статуси; рядки
alembic/           міграції
tests/             тести проти ASGI-застосунку
```
