# Блок `procurement`

Закупівлі: постачальники, замовлення, приходи за накладними, потреби від складу.

Публічний інтерфейс — [`contracts/procurement.yaml`](../../contracts/procurement.yaml).
Опис блоку — [`docs/procurement.md`](../../docs/procurement.md).

## Запуск

```bash
docker compose up -d postgres rabbitmq   # з кореня репозиторію
cd services/procurement
cp .env.example .env                     # RABBITMQ_URL — щоб склад отримував приходи
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8008
```

Документація API — http://localhost:8008/docs

## Перевірки

```bash
uv run pytest        # 12 тестів, SQLite у пам'яті, шина й catalog підмінені
uv run ruff check .
uv run mypy app
```

## Структура

```
app/config.py          налаштування з оточення, зокрема BUSINESS_TIMEZONE
app/db.py              сесія SQLAlchemy, власна схема
app/models.py          suppliers, orders, order_lines, receipts, receipt_lines, needs
app/money.py           гроші й кількість: Decimal усередині, рядок назовні
app/repository.py      запити; номер замовлення; чернетка для постачальника
app/handlers.py        stock.low → потреба й чернетка; stock.received → закрити потребу
app/consumer.py        слухач черги procurement.events: обробка → коміт → ack
app/catalog_client.py  деталь з catalog для рядка замовлення
app/events.py          публікація подій у шину
app/schemas.py         Pydantic — вони ж джерело OpenAPI
app/api/auth.py        хто робить запит і чи має право — з заголовків X-User-*
app/api/routes.py      ендпоінти, без SQL; статуси; приходи
alembic/               міграції
tests/                 тести проти ASGI-застосунку і обробників подій
```
