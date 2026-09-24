# Блок `inventory`

Склад: партії за FIFO, комірки, мінімальні залишки, резерви під наряди,
інвентаризація.

Публічний інтерфейс — [`contracts/inventory.yaml`](../../contracts/inventory.yaml).
Опис блоку — [`docs/inventory.md`](../../docs/inventory.md).

## Запуск

```bash
docker compose up -d postgres rabbitmq   # з кореня репозиторію
cd services/inventory
cp .env.example .env                     # RABBITMQ_URL — щоб бачити резерви
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8007
```

Документація API — http://localhost:8007/docs

## Перевірки

```bash
uv run pytest        # 17 тестів, SQLite у пам'яті, шина й catalog підмінені
uv run ruff check .
uv run mypy app
```

## Структура

```
app/config.py          налаштування з оточення
app/db.py              сесія SQLAlchemy, власна схема
app/models.py          items, lots, reservations, movements; UtcDateTime
app/money.py           гроші й кількість: Decimal усередині, рядок назовні
app/stock.py           залишки з партій, прихід, списання FIFO — вся арифметика
app/handlers.py        реакції на події catalog, work-orders і procurement
app/consumer.py        слухач черги inventory.events: обробка → коміт → ack
app/catalog_client.py  читання деталі з catalog для приходу
app/events.py          публікація подій у шину
app/schemas.py         Pydantic — вони ж джерело OpenAPI
app/repository.py      запити до бази
app/api/auth.py        хто робить запит і чи має право — з заголовків X-User-*
app/api/routes.py      ендпоінти, без SQL
alembic/               міграції
tests/                 тести проти ASGI-застосунку і обробників подій
```
