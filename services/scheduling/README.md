# Блок `scheduling`

Пости і записи клієнтів на них. Головне правило — пост не буває зайнятий
двічі — тримають і сервіс, і exclusion constraint у PostgreSQL.

Публічний інтерфейс — [`contracts/scheduling.yaml`](../../contracts/scheduling.yaml).
Опис блоку — [`docs/scheduling.md`](../../docs/scheduling.md).

## Запуск

```bash
docker compose up -d postgres rabbitmq   # з кореня репозиторію
cd services/scheduling
cp .env.example .env
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8005
```

Документація API — http://localhost:8005/docs

## Перевірки

```bash
uv run pytest        # 22 тести, SQLite у пам'яті, сусіди й шина підмінені
uv run ruff check .
uv run mypy app
```

Exclusion constraint є лише в PostgreSQL. На SQLite відмову бази імітує тест
`test_race_loser_gets_409_not_500`; на PostgreSQL це перевірено гонкою.

## Структура

```
app/config.py      налаштування з оточення, зокрема BUSINESS_TIMEZONE
app/db.py          сесія SQLAlchemy, власна схема
app/models.py      таблиці bays і appointments; UtcDateTime
app/schemas.py     Pydantic — вони ж джерело OpenAPI; правила проміжку часу
app/repository.py  запити до бази, без HTTP; пошук перетину; оновлення копій
app/peers.py       синхронне читання з customers і vehicles
app/consumer.py    слухач customer.updated і vehicle.updated
app/events.py      публікація подій у шину
app/api/auth.py    хто робить запит і чи має право — з заголовків X-User-*
app/api/routes.py  ендпоінти, без SQL; статуси; охорона запису від гонки
alembic/           міграції, зокрема btree_gist і EXCLUDE-constraint
tests/             тести проти ASGI-застосунку
```
