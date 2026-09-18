import type { AppModule } from '@baymeister/module-kit';

/**
 * Маніфест блоку `customers` — еталон для решти блоків.
 *
 * Це єдине, що каркас знає про модуль. Щоб блок ожив, у реєстрі каркаса
 * заглушка замінюється на цей об'єкт — більше нічого не змінюється.
 */
export const customersModule: AppModule = {
  id: 'customers',
  title: 'Клієнти',
  icon: 'users',
  status: 'ready',
  nav: { group: 'catalog', order: 10 },
  permissions: ['customers.read'],
  description: 'Клієнти фіз. і юр. осіб, контакти, історія звернень, сегменти.',
  routes: [
    { path: '/customers', lazy: () => import('./routes/list') },
    { path: '/customers/:customerId', lazy: () => import('./routes/detail') },
  ],
};
