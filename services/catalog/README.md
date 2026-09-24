# Блок `catalog`

Роботи з нормо-годинами, вартість нормо-години з історією, каталог запчастин.

Публічний інтерфейс — [`contracts/catalog.yaml`](../../contracts/catalog.yaml).
Опис блоку — [`docs/catalog.md`](../../docs/catalog.md).

## Запуск

```bash
docker compose up -d postgres          # з кореня репозиторію
cd services/catalog
cp .env.example .env
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8004
```

Документація API — http://localhost:8004/docs

## Перевірки

```bash
uv run pytest        # 19 тестів, SQLite у пам'яті, без зовнішніх залежностей
uv run ruff check .
uv run mypy app
```

## Структура

```
app/config.py      налаштування з оточення
app/db.py          сесія SQLAlchemy, власна схема
app/models.py      таблиці labor_rates, services, parts
app/money.py       гроші й нормо-години: Decimal усередині, рядок назовні
app/schemas.py     Pydantic — вони ж джерело OpenAPI; нормалізація кодів
app/repository.py  запити до бази, без HTTP; ставка на момент часу
app/api/auth.py    хто робить запит і чи має право — з заголовків X-User-*
app/api/routes.py  ендпоінти, без SQL; ціна роботи рахується тут
app/events.py      публікація подій у шину
alembic/           міграції
tests/             тести проти ASGI-застосунку
```
