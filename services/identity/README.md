# Блок `identity`

Співробітники, ролі й права, вхід і токени доступу.

Публічний інтерфейс — [`contracts/identity.yaml`](../../contracts/identity.yaml).
Опис блоку — [`docs/identity.md`](../../docs/identity.md).

## Запуск

```bash
docker compose up -d postgres          # з кореня репозиторію
cd services/identity
cp .env.example .env
uv sync --group dev
uv run alembic upgrade head
uv run python -m app.bootstrap         # перший власник, якщо база порожня
uv run uvicorn app.main:app --reload --port 8002
```

Документація API — http://localhost:8002/docs

Без `JWT_PRIVATE_KEY_FILE` ключ підпису тимчасовий: після перезапуску всі
токени недійсні. Для проду — див. `.env.example`.

## Перевірки

```bash
uv run pytest        # 15 тестів, SQLite у пам'яті, без зовнішніх залежностей
uv run ruff check .
uv run mypy app
```

## Структура

```
app/config.py      налаштування з оточення
app/db.py          сесія SQLAlchemy, власна схема
app/models.py      таблиця users
app/roles.py       каталог ролей і їхніх прав — код, а не таблиця
app/security.py    хеші паролів (argon2), підпис токенів (RS256), JWKS
app/schemas.py     Pydantic — вони ж джерело OpenAPI
app/repository.py  запити до бази, без HTTP
app/api/auth.py    хто робить запит — з заголовків X-User-*, зразок для всіх блоків
app/api/routes.py  ендпоінти, без SQL
app/events.py      публікація подій у шину
app/bootstrap.py   створення першого власника
alembic/           міграції
tests/             тести проти ASGI-застосунку
```
