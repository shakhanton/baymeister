import type { AppModule } from '@baymeister/module-kit';
import { assertRegistryIsValid } from '@baymeister/module-kit';
import { catalogModule } from '@baymeister/module-catalog';
import { customersModule } from '@baymeister/module-customers';
import { identityModule } from '@baymeister/module-identity';
import { inventoryModule } from '@baymeister/module-inventory';
import { schedulingModule } from '@baymeister/module-scheduling';
import { vehiclesModule } from '@baymeister/module-vehicles';
import { workOrdersModule } from '@baymeister/module-work-orders';

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
  schedulingModule,
  workOrdersModule,
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
  customersModule,
  vehiclesModule,
  catalogModule,

  // ── Склад ───────────────────────────────────────────────────────────────
  inventoryModule,
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
  identityModule,
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
