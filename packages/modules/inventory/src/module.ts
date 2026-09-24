import type { AppModule } from '@baymeister/module-kit';

/** Маніфест блоку `inventory`. */
export const inventoryModule: AppModule = {
  id: 'inventory',
  title: 'Склад',
  icon: 'package',
  status: 'ready',
  nav: { group: 'warehouse', order: 10 },
  permissions: ['inventory.read'],
  description: 'Залишки за FIFO, комірки, резерви, штрихкоди, інвентаризація.',
  routes: [
    { path: '/inventory', lazy: () => import('./routes/list') },
    { path: '/inventory/:partId', lazy: () => import('./routes/detail') },
  ],
};
