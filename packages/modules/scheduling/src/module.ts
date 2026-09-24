import type { AppModule } from '@baymeister/module-kit';

/** Маніфест блоку `scheduling`. */
export const schedulingModule: AppModule = {
  id: 'scheduling',
  title: 'Планувальник',
  icon: 'calendar-days',
  status: 'ready',
  nav: { group: 'operations', order: 10 },
  permissions: ['scheduling.read'],
  description: 'Записи, пости й підйомники, завантаження механіків, онлайн-бронювання.',
  routes: [{ path: '/scheduling', lazy: () => import('./routes/board') }],
};
