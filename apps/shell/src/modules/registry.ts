import type { AppModule } from '@baymeister/module-kit';
import { assertRegistryIsValid } from '@baymeister/module-kit';

/**
 * Реєстр модулів — єдине джерело правди про склад продукту.
 *
 * Тут перелічені всі блоки, зокрема ті, яких ще не існує. Саме тому меню повне з
 * першого дня: неготовий блок видно як сірий пункт, а не як порожнечу.
 *
 * ІНТЕГРАЦІЯ ГОТОВОГО БЛОКУ
 * ─────────────────────────
 * 1. Імпортувати маніфест із пакета модуля:
 *      import { customersModule } from '@baymeister/module-customers';
 * 2. Замінити ним заглушку в цьому масиві.
 * Більше нічого в каркасі міняти не треба.
 *
 * Сервіси `gateway` і `files` у реєстрі відсутні свідомо — вони не мають
 * інтерфейсу. Їхній опис у docs/architecture.md.
 */
export const registry: AppModule[] = [
  // ── Операції ────────────────────────────────────────────────────────────
  {
    id: 'scheduling',
    title: 'Планувальник',
    icon: 'calendar-days',
    status: 'planned',
    nav: { group: 'operations', order: 10 },
    permissions: ['scheduling.read'],
    routes: [],
    description: 'Записи, пости й підйомники, завантаження механіків, онлайн-бронювання.',
  },
  {
    id: 'work-orders',
    title: 'Наряд-замовлення',
    icon: 'clipboard-list',
    status: 'planned',
    nav: { group: 'operations', order: 20 },
    permissions: ['work_orders.read'],
    routes: [],
    description: 'Ядро системи: роботи, деталі, статуси, хронометраж.',
  },
  {
    id: 'inspections',
    title: 'Огляди',
    icon: 'search-check',
    status: 'planned',
    nav: { group: 'operations', order: 30 },
    permissions: ['inspections.read'],
    routes: [],
    description: 'Чек-листи огляду, фото й відео, рекомендації клієнту.',
  },

  // ── Довідники ───────────────────────────────────────────────────────────
  {
    id: 'customers',
    title: 'Клієнти',
    icon: 'users',
    status: 'planned',
    nav: { group: 'catalog', order: 10 },
    permissions: ['customers.read'],
    routes: [],
    description: 'Клієнти фіз. і юр. осіб, контакти, історія звернень, сегменти.',
  },
  {
    id: 'vehicles',
    title: 'Автомобілі',
    icon: 'car',
    status: 'planned',
    nav: { group: 'catalog', order: 20 },
    permissions: ['vehicles.read'],
    routes: [],
    description: 'Автопарк клієнтів, VIN, сервісна книжка, пробіг.',
  },
  {
    id: 'catalog',
    title: 'Послуги та прайс',
    icon: 'book-open',
    status: 'planned',
    nav: { group: 'catalog', order: 30 },
    permissions: ['catalog.read'],
    routes: [],
    description: 'Послуги, нормо-години, прайс-листи, каталог запчастин.',
  },

  // ── Склад ───────────────────────────────────────────────────────────────
  {
    id: 'inventory',
    title: 'Склад',
    icon: 'package',
    status: 'planned',
    nav: { group: 'warehouse', order: 10 },
    permissions: ['inventory.read'],
    routes: [],
    description: 'Залишки за FIFO, комірки, резерви, штрихкоди, інвентаризація.',
  },
  {
    id: 'procurement',
    title: 'Закупівлі',
    icon: 'truck',
    status: 'planned',
    nav: { group: 'warehouse', order: 20 },
    permissions: ['procurement.read'],
    routes: [],
    description: 'Постачальники, замовлення по API, прибуткові накладні.',
  },

  // ── Фінанси ─────────────────────────────────────────────────────────────
  {
    id: 'finance',
    title: 'Каса та розрахунки',
    icon: 'wallet',
    status: 'planned',
    nav: { group: 'finance', order: 10 },
    permissions: ['finance.read'],
    routes: [],
    description: 'Платежі, взаєморозрахунки, фіскалізація.',
  },
  {
    id: 'payroll',
    title: 'Зарплата',
    icon: 'hand-coins',
    status: 'planned',
    nav: { group: 'finance', order: 20 },
    permissions: ['payroll.read'],
    routes: [],
    description: 'Нарахування механікам, правила оплати, табель, KPI.',
  },
  {
    id: 'documents',
    title: 'Документи',
    icon: 'file-text',
    status: 'planned',
    nav: { group: 'finance', order: 30 },
    permissions: ['documents.read'],
    routes: [],
    description: 'Друковані форми, акти, накладні, генерація PDF.',
  },

  // ── Аналітика ───────────────────────────────────────────────────────────
  {
    id: 'analytics',
    title: 'Звіти',
    icon: 'line-chart',
    status: 'planned',
    nav: { group: 'insights', order: 10 },
    permissions: ['analytics.read'],
    routes: [],
    description: 'Дашборд керівника, виручка, середній чек, KPI механіків.',
  },

  // ── Налаштування ────────────────────────────────────────────────────────
  {
    id: 'identity',
    title: 'Користувачі та ролі',
    icon: 'user-cog',
    status: 'planned',
    nav: { group: 'settings', order: 10 },
    permissions: ['identity.read'],
    routes: [],
    description: 'Співробітники, ролі, права доступу, сесії.',
  },
  {
    id: 'notifications',
    title: 'Сповіщення',
    icon: 'bell',
    status: 'planned',
    nav: { group: 'settings', order: 20 },
    permissions: ['notifications.read'],
    routes: [],
    description: 'SMS, email, Viber; шаблони й статуси доставки.',
  },
  {
    id: 'integrations',
    title: 'Інтеграції',
    icon: 'plug',
    status: 'planned',
    nav: { group: 'settings', order: 30 },
    permissions: ['integrations.read'],
    routes: [],
    description: 'Телефонія, ЄДР, VIN-декодер, каталоги запчастин, фіскалізація.',
  },
];

assertRegistryIsValid(registry);
