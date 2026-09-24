# Блок `scheduling`

Пости (підйомники, ями, стенди, мийка) і записи клієнтів на них. Дошка на
день: колонка на пост, вісь часу, клік по вільній клітинці — запис.

## Чотири артефакти блоку

| Артефакт | Де лежить | Що це |
|---|---|---|
| Контракт | [`contracts/scheduling.yaml`](../contracts/scheduling.yaml) | OpenAPI 3.1, публічний інтерфейс |
| Сервіс | [`services/scheduling/`](../services/scheduling/) | FastAPI + власна схема в PostgreSQL |
| Фронтенд-модуль | [`packages/modules/scheduling/`](../packages/modules/scheduling/) | дошка на день |
| Документація | цей файл | правило неперетину, статуси, межі |

## Що блок віддає

| Метод | Шлях | Право | Що робить |
|---|---|---|---|
| `GET` | `/scheduling/bays` | `scheduling.read` | пости в порядку колонок |
| `POST` | `/scheduling/bays` | `scheduling.write` | додати пост |
| `PATCH` | `/scheduling/bays/{id}` | `scheduling.write` | перейменувати, змінити тип чи порядок |
| `POST` | `/scheduling/bays/{id}/archive` | `scheduling.write` | прибрати з дошки; 409, якщо є майбутні записи |
| `GET` | `/scheduling/appointments?from=&to=` | `scheduling.read` | записи, що перетинають проміжок (≤ 31 дня) |
| `POST` | `/scheduling/appointments` | `scheduling.write` | записати клієнта |
| `GET` | `/scheduling/appointments/{id}` | `scheduling.read` | один запис |
| `PATCH` | `/scheduling/appointments/{id}` | `scheduling.write` | перенести (лише `booked`) або змінити примітку |
| `POST` | `/scheduling/appointments/{id}/status` | `scheduling.write` | змінити статус |

## Головне правило: пост не буває зайнятий двічі

Записи зі статусом `booked` або `arrived` на одному посту не перетинаються.
Межі напіввідкриті: запис до 11:00 і запис з 11:00 не конфліктують.

Правило тримається двічі:

1. **Сервіс** перед записом шукає перетин і відповідає 409 з поясненням:
   «Підйомник 1 зайнятий з 15.06 10:00 до 15.06 11:30: Петренко».
2. **База** — `EXCLUDE USING gist (bay_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)`
   для активних статусів. Перевірка й запис не атомарні: два одночасні запити
   можуть обидва пройти крок 1. Другий зупиняє constraint, і клієнт отримує
   таку саму 409: «Цей час на посту щойно зайняли».

Перевірено на PostgreSQL: 20 одночасних записів на той самий слот (з
навмисною затримкою, щоб усі пройшли крок 1) — 1 створено, 14 зупинив
constraint, 5 — перевірка сервісу, жодної 500. Помилка constraint приходить
уже на `flush`, не на `commit`, — тому під охороною весь запис.

`btree_gist` — «довірене» розширення: міграція ставить його від імені власника
бази, суперюзер не потрібен.

## Статуси

| з | у |
|---|---|
| `booked` | `arrived`, `cancelled`, `no_show` |
| `arrived` | `completed`, `cancelled` |

`completed`, `cancelled`, `no_show` — кінцеві. Скасування й неявка звільняють
пост. Переносити можна лише `booked` — приїхав, значить пізно. Дошка показує
лише дозволені кнопки, але правила тримає бекенд.

## Час

- В API й базі — завжди UTC із поясом. Час без поясу — 422: «10:00» у Києві і
  в UTC — різні записи.
- Дошка показує місцевий час браузера й надсилає ISO з поясом.
- Години в повідомленнях для людей — у поясі сервісу (`BUSINESS_TIMEZONE`,
  за замовчуванням `Europe/Kyiv`), щоб збігались із дошкою.
- Тип стовпця `UtcDateTime` повертає час із поясом і на PostgreSQL, і на
  SQLite у тестах.

## Звʼязок із `customers` і `vehicles`

Як у `vehicles`: при записі сервіс перевіряє клієнта й авто через їхні API від
імені того самого користувача (заголовки `X-User-*`), перевіряє, що авто —
саме цього клієнта, і зберігає копії імені, телефону й «AA1234BC · Volkswagen
Golf». Далі копії оновлюються подіями `customer.updated` і `vehicle.updated` —
ідемпотентно й за часом події (`app/consumer.py`). Дошка не робить жодного
запиту до сусідів.

Спершу перевіряється перетин у своїй базі, потім — сусіди: зайнятий слот не
коштує мережевих запитів.

## Що блок публікує

| Подія | Коли | Хто слухає і навіщо |
|---|---|---|
| `appointment.booked` | записано | `notifications` — SMS-підтвердження |
| `appointment.rescheduled` | перенесено | `notifications` — нове нагадування |
| `appointment.arrived` | клієнт приїхав | `work-orders` — підказка відкрити наряд |
| `appointment.completed` | завершено | `analytics` — завантаження постів |
| `appointment.cancelled` / `no_show` | скасовано / не приїхав | `analytics` — частка неявок |

## Запуск

```bash
docker compose up -d postgres rabbitmq
cd services/scheduling
cp .env.example .env
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8005
```

## Перевірки

```bash
cd services/scheduling
uv run pytest         # 22 тести
uv run ruff check .
uv run mypy app

cd ../..
pnpm --filter @baymeister/module-scheduling typecheck
```

## Що лишилось зробити

- Робочі години й вихідні — зараз дошка показує 08:00–20:00 для всіх постів.
- Механік на запис (`mechanic_id` з `identity`) і його завантаження.
- Перетягування запису мишею — API перенесення вже є.
- Онлайн-запис клієнтом без входу — окремий публічний ендпоінт через gateway.
