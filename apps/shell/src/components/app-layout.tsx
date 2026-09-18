import { Suspense } from 'react';
import { Outlet, useLocation } from 'react-router';
import { registry } from '../modules/registry';
import { Header } from './header';
import { Sidebar } from './sidebar';

function usePageTitle(): string {
  const { pathname } = useLocation();
  if (pathname === '/') return 'Огляд';
  if (pathname === '/roadmap') return 'Стан блоків';

  const module = registry.find((m) => m.routes.some((r) => pathname.startsWith(r.path.split('/:')[0]!)));
  return module?.title ?? 'Baymeister';
}

export function AppLayout() {
  const title = usePageTitle();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header title={title} />
        <main className="flex-1 overflow-y-auto px-6 py-6">
          <Suspense fallback={<PageSkeleton />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="flex flex-col gap-3" role="status" aria-label="Завантаження">
      <div className="h-8 w-56 animate-pulse rounded-bm bg-surface-2" />
      <div className="h-32 animate-pulse rounded-bm bg-surface-2" />
    </div>
  );
}
