import type { AppModule } from '@baymeister/module-kit';

/** Маніфест блоку `procurement`. */
export const procurementModule: AppModule = {
  id: 'procurement',
  title: 'Закупівлі',
  icon: 'truck',
  status: 'ready',
  nav: { group: 'warehouse', order: 20 },
  permissions: ['procurement.read'],
  description: 'Постачальники, замовлення, приходи за накладними, потреби від складу.',
  routes: [
    { path: '/procurement', lazy: () => import('./routes/orders') },
    { path: '/procurement/orders/:orderId', lazy: () => import('./routes/order') },
    { path: '/procurement/needs', lazy: () => import('./routes/needs') },
    { path: '/procurement/suppliers', lazy: () => import('./routes/suppliers') },
  ],
};
