# Baymeister

CRM для автосервісу. Монорепозиторій: фронтенд-каркас, фронтенд-модулі блоків і
бекенд-сервіси.

Архітектура — [`docs/architecture.md`](docs/architecture.md).

## Запуск

```bash
corepack enable pnpm
pnpm install
pnpm dev                      # каркас на http://localhost:5173
```

Каркас пускає тільки після входу, тому для роботи потрібні три сервіси:
`identity` (вхід), `gateway` (єдина точка входу) і бекенд блоку.

```bash
docker compose up -d postgres rabbitmq

cd services/identity && cp .env.example .env && uv sync --group dev
uv run alembic upgrade head && uv run python -m app.bootstrap
uv run uvicorn app.main:app --reload --port 8002          # окремий термінал

cd services/customers && cp .env.example .env && uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8001          # окремий термінал

cd services/vehicles && cp .env.example .env && uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8003          # окремий термінал

cd services/catalog && cp .env.example .env && uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8004          # окремий термінал

cd services/gateway && uv sync --group dev
uv run uvicorn app.main:app --reload --port 8000          # окремий термінал
```

Вхід — `owner@example.com` / `change-me-please` (задається в
`services/identity/.env`). Дев-сервер Vite проксіює `/api` на gateway `:8000`.

> Postgres створює бази блоків тільки на порожньому томі. Якщо том лишився
> з часів, коли баз нових блоків ще не було:
> `docker compose exec postgres createdb -U baymeister identity` (і так само `vehicles`, `catalog`).

## Структура

```
apps/shell/            каркас: меню, маршрути, авторизація, реєстр блоків
packages/ui/           дизайн-система — токени й базові компоненти
packages/module-kit/   контракт між каркасом і блоками (тип AppModule)
packages/modules/*     фронтенд-модулі блоків, по одному на виконавця
services/gateway/      єдина точка входу: перевірка токена, маршрутизація
services/*             бекенд-сервіси на FastAPI, по одному на блок
contracts/*.yaml       OpenAPI-специфікації, публічні інтерфейси блоків
docs/                  архітектура й опис окремих блоків
```

## Еталонний блок

`customers` доведений до кінця і слугує зразком: контракт, сервіс,
фронтенд-модуль, тести, документація. Опис — [`docs/customers.md`](docs/customers.md).
Беручись за свій блок, копіюйте його структуру, а не вигадуйте власну.

## Як додати блок

Блок — це вертикальний зріз: сервіс, контракт, фронтенд-модуль і документація в
одному володінні. Виконавець блоку не змінює файли каркаса, крім одного рядка в
реєстрі.

1. **Контракт першим.** Описати `contracts/<блок>.yaml` (OpenAPI 3.1) і
   змерджити окремим PR до початку реалізації.
2. **Сервіс.** `services/<блок>/` — FastAPI, власна схема в PostgreSQL. У чужі
   таблиці не ходити: тільки через API або події. Права перевіряти через
   `app/api/auth.py` (скопіювати з `customers`); підключити блок у gateway —
   рядок у `UPSTREAMS`.
3. **Фронтенд-модуль.** `packages/modules/<блок>/` з маніфестом:

   ```ts
   import type { AppModule } from '@baymeister/module-kit';

   export const inventoryModule: AppModule = {
     id: 'inventory',
     title: 'Склад',
     icon: 'package',
     status: 'ready',
     nav: { group: 'warehouse', order: 10 },
     permissions: ['inventory.read'],
     routes: [
       { path: '/inventory', lazy: () => import('./routes/List') },
     ],
   };
   ```

4. **Реєстр.** У `apps/shell/src/modules/registry.ts` замінити заглушку блоку на
   імпортований маніфест. Пункт меню перестане бути сірим сам.

Поки `status !== 'ready'`, маршрути модуля не реєструються взагалі — незавершений
блок не може зламати навігацію, навіть якщо його код уже в репозиторії.

## Команди

| Команда | Що робить |
|---|---|
| `pnpm dev` | дев-сервер каркаса |
| `pnpm build` | збірка всіх пакетів |
| `pnpm typecheck` | перевірка типів |
| `pnpm lint` | лінт |
| `pnpm test` | тести |

## Внесок

Перед першим PR бот попросить підписати [CLA](CLA.md) — один коментар,
один раз. Без підпису merge заблоковано.
