import type { AppModule } from '@baymeister/module-kit';

/** Маніфест блоку `work-orders` — ядра системи. */
export const workOrdersModule: AppModule = {
  id: 'work-orders',
  title: 'Наряд-замовлення',
  icon: 'clipboard-list',
  status: 'ready',
  nav: { group: 'operations', order: 20 },
  permissions: ['work_orders.read'],
  description: 'Ядро системи: роботи, деталі, статуси, хронометраж.',
  routes: [
    { path: '/work-orders', lazy: () => import('./routes/list') },
    { path: '/work-orders/:orderId', lazy: () => import('./routes/detail') },
  ],
};
