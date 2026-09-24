import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo } from 'react';
import { RouterProvider } from 'react-router';
import { restoreSession, useAuth } from './auth/permissions';
import { createAppRouter } from './router';
import Login from './routes/login';

/**
 * Ворота каркаса: без сесії — екран входу, із сесією — застосунок.
 *
 * Роутер створюється, коли відомий користувач, бо набір маршрутів залежить від
 * його прав. Вихід скидає і роутер, і кеш запитів — дані попереднього
 * користувача не мають пережити зміну сесії.
 */
export function App() {
  const status = useAuth((s) => s.status);
  const user = useAuth((s) => s.user);
  const queryClient = useQueryClient();

  useEffect(() => {
    void restoreSession();
  }, []);

  useEffect(() => {
    if (status === 'anonymous') queryClient.clear();
  }, [status, queryClient]);

  const router = useMemo(() => (user ? createAppRouter() : null), [user]);

  if (status === 'restoring') return <Splash />;
  if (!router) return <Login />;
  return <RouterProvider router={router} />;
}

function Splash() {
  return (
    <div className="flex h-screen items-center justify-center" role="status" aria-label="Завантаження">
      <span className="font-cond text-xl font-bold tracking-tight text-ink-faint">Baymeister</span>
    </div>
  );
}
