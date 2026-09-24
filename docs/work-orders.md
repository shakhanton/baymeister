# Блок `work-orders`

Ядро системи. Наряд — хто приїхав, на чому, що зробили, які деталі поставили й
скільки це коштує. Сюди сходяться всі блоки Фази 1: клієнт (`customers`), авто
(`vehicles`), ціни (`catalog`), запис (`scheduling`).

## Чотири артефакти блоку

| Артефакт | Де лежить | Що це |
|---|---|---|
| Контракт | [`contracts/work-orders.yaml`](../contracts/work-orders.yaml) | OpenAPI 3.1, публічний інтерфейс |
| Сервіс | [`services/work-orders/`](../services/work-orders/) | FastAPI + власна схема в PostgreSQL |
| Фронтенд-модуль | [`packages/modules/work-orders/`](../packages/modules/work-orders/) | список, відкриття, наряд з рядками й сумами |
| Документація | цей файл | ціни, статуси, номери, межі |

## Що блок віддає

| Метод | Шлях | Право | Що робить |
|---|---|---|---|
| `GET` | `/work-orders` | `work_orders.read` | список: пошук за номером, держномером, клієнтом; фільтри |
| `POST` | `/work-orders` | `work_orders.write` | відкрити наряд |
| `GET` | `/work-orders/{id}` | `work_orders.read` | наряд із рядками й сумами |
| `PATCH` | `/work-orders/{id}` | `work_orders.write` | скарга, пробіг, примітка |
| `POST` | `/work-orders/{id}/status` | `work_orders.write` | змінити статус |
| `POST` | `/work-orders/{id}/lines` | `work_orders.write` + `catalog.read` | додати роботу чи запчастину з прайсу |
| `PATCH` | `/work-orders/{id}/lines/{lineId}` | `work_orders.write` | змінити кількість |
| `DELETE` | `/work-orders/{id}/lines/{lineId}` | `work_orders.write` | прибрати рядок |

## Як потрапляє наряд

```
 scheduling: запис → «Приїхав» → «Відкрити наряд»
                                   │  /work-orders?new=1&customer=…&vehicle=…&appointment=…
                                   ▼
 work-orders: клієнт і авто вже обрані → скарга, пробіг → наряд 2026-00042
```

Планувальник посилається на наряди лише URL-ом — модулі не імпортують один
одного. Наряд можна відкрити й напряму, без запису.

## Ціни фіксуються

- **Рядок** бере назву, код і ціну з `catalog` у момент додавання й більше не
  змінюється. Нова ставка нормо-години чи нова ціна фільтра не переписують ні
  відкриті, ні закриті наряди — клієнту вже назвали суму.
- **Знижка клієнта** фіксується при відкритті наряду з `customers`.
- Робота без ціни (ставку ще не задано) чи архівна позиція — 422 з підказкою,
  що зробити.

## Суми

Рахуються при читанні з рядків, у базі не зберігаються — «разом» не може
розійтися з рядками.

```
сума рядка = кількість × ціна                      до копійки
знижка     = (роботи + запчастини) × знижка %      до копійки
до сплати  = роботи + запчастини − знижка
```

Округлення — половина вгору: 5 % від 245.50 = 12.275 → 12.28. Гроші й
кількість — рядками (`"1147.50"`, `"4.500"`), як у `catalog`.

## Статуси

| з | у |
|---|---|
| `open` (прийнято) | `in_progress`, `cancelled` |
| `in_progress` (в роботі) | `done`, `cancelled` |
| `done` (роботи завершено) | `closed`, `in_progress` |

`closed` (видано) і `cancelled` — кінцеві. Рядки, скарга й пробіг змінюються
лише в `open` та `in_progress`; примітку можна дописати й до закритого.
`done` без жодного рядка неможливий — порожній наряд лише скасовують.

## Номер наряду

`2026-00042` — рік за місцевим часом сервісу (`BUSINESS_TIMEZONE`) і порядковий
номер у ньому. Видається одним `UPDATE … RETURNING` над рядком лічильника року —
рядок блокується до кінця транзакції. Перевірено на PostgreSQL: 30 одночасних
відкриттів — 30 різних номерів без пропусків.

## Що блок публікує

| Подія | Коли | Хто слухає і навіщо |
|---|---|---|
| `order.created` | відкрито | `scheduling` — повʼязати з записом; `analytics` |
| `order.started` | в роботу | `analytics` — час очікування |
| `order.completed` | роботи завершено | `finance` — рахунок; `payroll` — нарахування; `notifications` — «авто готове» |
| `order.closed` | видано | `analytics` — виручка |
| `order.cancelled` | скасовано | `inventory` — зняти всі резерви |
| `parts.reserved` / `parts.released` | додано / прибрано запчастину | `inventory` — резерв на складі |

Слухає `customer.updated` і `vehicle.updated` — оновлює копії імені, телефону й
держномера, як `vehicles` і `scheduling`.

## Запуск

```bash
docker compose up -d postgres rabbitmq
cd services/work-orders
cp .env.example .env
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8006
```

## Перевірки

```bash
cd services/work-orders
uv run pytest         # 19 тестів
uv run ruff check .
uv run mypy app

cd ../..
pnpm --filter @baymeister/module-work-orders typecheck
```

## Що лишилось зробити

- Механік на рядок роботи й хронометраж — для `payroll`.
- Друк наряду й акту — блок `documents`.
- Оплата — блок `finance` слухає `order.completed`.
- Резерв на складі — блок `inventory` слухає `parts.reserved`.
