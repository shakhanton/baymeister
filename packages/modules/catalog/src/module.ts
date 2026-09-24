import type { AppModule } from '@baymeister/module-kit';

/** Маніфест блоку `catalog`. */
export const catalogModule: AppModule = {
  id: 'catalog',
  title: 'Послуги та прайс',
  icon: 'book-open',
  status: 'ready',
  nav: { group: 'catalog', order: 30 },
  permissions: ['catalog.read'],
  description: 'Послуги, нормо-години, прайс-листи, каталог запчастин.',
  routes: [
    { path: '/catalog', lazy: () => import('./routes/services') },
    { path: '/catalog/parts', lazy: () => import('./routes/parts') },
  ],
};
