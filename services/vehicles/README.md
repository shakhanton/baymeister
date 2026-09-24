# Блок `vehicles`

Автомобілі клієнтів: держномер, VIN, марка, модель, рік, історія пробігу.

Публічний інтерфейс — [`contracts/vehicles.yaml`](../../contracts/vehicles.yaml).
Опис блоку — [`docs/vehicles.md`](../../docs/vehicles.md).

## Запуск

```bash
docker compose up -d postgres rabbitmq   # з кореня репозиторію
cd services/vehicles
cp .env.example .env
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8003
```

Документація API — http://localhost:8003/docs

## Перевірки

```bash
uv run pytest        # 26 тестів, SQLite у пам'яті, customers і шина підмінені
uv run ruff check .
uv run mypy app
```

## Структура

```
app/config.py            налаштування з оточення
app/db.py                сесія SQLAlchemy, власна схема
app/models.py            таблиці vehicles і mileage_readings
app/schemas.py           Pydantic — вони ж джерело OpenAPI; нормалізація номера й VIN
app/repository.py        запити до бази, без HTTP; оновлення копії власника
app/customers_client.py  синхронне читання клієнта з customers
app/consumer.py          слухач подій з шини — зразок для інших блоків
app/events.py            публікація подій у шину
app/api/auth.py          хто робить запит і чи має право — з заголовків X-User-*
app/api/routes.py        ендпоінти, без SQL
alembic/                 міграції
tests/                   тести проти ASGI-застосунку і обробника подій
```
