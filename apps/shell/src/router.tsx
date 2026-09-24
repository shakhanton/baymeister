import { liveRoutes } from '@baymeister/module-kit';
import { createBrowserRouter, type RouteObject } from 'react-router';
import { canStatic } from './auth/permissions';
import { AppLayout } from './components/app-layout';
import { registry } from './modules/registry';
import Dashboard from './routes/dashboard';
import NotFound from './routes/not-found';
import Roadmap from './routes/roadmap';

/**
 * Маршрути модулів беруться тільки з блоків зі status='ready', на які в
 * користувача є права.
 *
 * Тому неготовий блок не може зламати навігацію: його екранів у роутері немає
 * взагалі, і прямий перехід за URL дає 404, а не білий екран. Роутер
 * будується після входу — у кожного користувача власний набір маршрутів.
 */
export function createAppRouter() {
  const moduleRoutes: RouteObject[] = liveRoutes(registry, canStatic).map((route) => ({
    path: route.path,
    lazy: async () => ({ Component: (await route.lazy()).default }),
  }));

  return createBrowserRouter([
    {
      path: '/',
      element: <AppLayout />,
      errorElement: <NotFound />,
      children: [
        { index: true, element: <Dashboard /> },
        { path: 'roadmap', element: <Roadmap /> },
        ...moduleRoutes,
        { path: '*', element: <NotFound /> },
      ],
    },
  ]);
}
