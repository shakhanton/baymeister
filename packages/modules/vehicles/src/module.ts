import type { AppModule } from '@baymeister/module-kit';

/** Маніфест блоку `vehicles`. */
export const vehiclesModule: AppModule = {
  id: 'vehicles',
  title: 'Автомобілі',
  icon: 'car',
  status: 'ready',
  nav: { group: 'catalog', order: 20 },
  permissions: ['vehicles.read'],
  description: 'Автопарк клієнтів, VIN, сервісна книжка, пробіг.',
  routes: [
    { path: '/vehicles', lazy: () => import('./routes/list') },
    { path: '/vehicles/:vehicleId', lazy: () => import('./routes/detail') },
  ],
};
