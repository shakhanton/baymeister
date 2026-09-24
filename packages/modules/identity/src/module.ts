import type { AppModule } from '@baymeister/module-kit';

/**
 * Маніфест блоку `identity`.
 *
 * Вхід і сесія — справа каркаса; цей модуль — лише екрани керування
 * співробітниками для тих, хто має право `identity.read`.
 */
export const identityModule: AppModule = {
  id: 'identity',
  title: 'Користувачі та ролі',
  icon: 'user-cog',
  status: 'ready',
  nav: { group: 'settings', order: 10 },
  permissions: ['identity.read'],
  description: 'Співробітники, ролі, права доступу, сесії.',
  routes: [
    { path: '/users', lazy: () => import('./routes/list') },
    { path: '/users/:userId', lazy: () => import('./routes/detail') },
  ],
};
