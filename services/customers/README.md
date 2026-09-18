# Блок `customers`

Клієнти автосервісу: фізичні та юридичні особи, контакти, знижки.

Публічний інтерфейс — [`contracts/customers.yaml`](../../contracts/customers.yaml).
Контракт головніший за код: якщо вони розійшлись, виправляється код.

## Запуск

```bash
docker compose up -d postgres          # з кореня репозиторію
cd services/customers
cp .env.example .env
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8001
```

Документація API — http://localhost:8001/docs

## Перевірки

```bash
uv run pytest        # 11 тестів, SQLite у пам'яті, без зовнішніх залежностей
uv run ruff check .
uv run mypy app
```

## Що блок публікує

| Подія | Коли | Хто слухає |
|---|---|---|
| `customer.created` | створено клієнта | `notifications` |
| `customer.updated` | змінено ім'я або телефон | `vehicles`, `work-orders` — оновлюють власну копію |
| `customer.archived` | клієнта архівовано | `analytics` |

Без `RABBITMQ_URL` події пишуться в лог — блок піднімається і працює без брокера.

## Межі

Блок **не** зберігає автомобілі, наряди чи платежі. Ці блоки тримають у себе
`customer_id` і власну копію імені з телефоном, оновлювану за `customer.updated`.
Дублювання тут навмисне: інакше кожен список нарядів перетворюється на віяло
запитів до цього сервісу.

Архівування — м'яке. Клієнт зникає зі списків, але лишається доступним за
ідентифікатором, бо наряди й автомобілі на нього посилаються.

## Структура

```
app/config.py      налаштування з оточення
app/db.py          сесія SQLAlchemy, власна схема
app/models.py      таблиця customers
app/schemas.py     Pydantic — вони ж джерело OpenAPI
app/repository.py  запити до бази, без HTTP
app/api/routes.py  ендпоінти, без SQL
app/events.py      публікація подій у шину
alembic/           міграції
tests/             тести проти ASGI-застосунку
```

Розділення `repository` і `routes` навмисне: логіка запитів тестується без HTTP,
а маршрути не знають про SQL.
