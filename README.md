# Baymeister

CRM для автосервісу. Монорепозиторій: фронтенд-каркас, фронтенд-модулі блоків і
бекенд-сервіси.

Архітектура — [`docs/architecture.md`](docs/architecture.md).

## Запуск

```bash
corepack enable pnpm
pnpm install
pnpm dev
```

Каркас підніметься на http://localhost:5173. Бекенда поки немає; запити на
`/api` проксіюються на `localhost:8000`, де очікується gateway.

## Структура

```
apps/shell/            каркас: меню, маршрути, авторизація, реєстр блоків
packages/ui/           дизайн-система — токени й базові компоненти
packages/module-kit/   контракт між каркасом і блоками (тип AppModule)
packages/modules/*     фронтенд-модулі блоків, по одному на виконавця
services/*             бекенд-сервіси на FastAPI, по одному на блок
contracts/*.yaml       OpenAPI-специфікації, публічні інтерфейси блоків
docs/                  архітектура й опис окремих блоків
```

## Як додати блок

Блок — це вертикальний зріз: сервіс, контракт, фронтенд-модуль і документація в
одному володінні. Виконавець блоку не змінює файли каркаса, крім одного рядка в
реєстрі.

1. **Контракт першим.** Описати `contracts/<блок>.yaml` (OpenAPI 3.1) і
   змерджити окремим PR до початку реалізації.
2. **Сервіс.** `services/<блок>/` — FastAPI, власна схема в PostgreSQL. У чужі
   таблиці не ходити: тільки через API або події.
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
