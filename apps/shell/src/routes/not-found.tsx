import { EmptyState } from '@baymeister/ui';
import { Link, useRouteError } from 'react-router';

export default function NotFound() {
  const error = useRouteError();
  const isMissing = !error || (error as { status?: number }).status === 404;

  return (
    <div className="flex h-screen items-center justify-center p-6">
      <EmptyState
        className="max-w-lg bg-surface"
        title={isMissing ? 'Сторінки немає' : 'Щось пішло не так'}
        description={
          isMissing
            ? 'Такого маршруту не існує. Можливо, блок, до якого він належить, ще не інтегрований — тоді його пункт у меню сірий.'
            : 'Сталася помилка під час завантаження екрана. Спробуйте оновити сторінку.'
        }
        action={
          <Link
            to="/"
            className="inline-flex h-9 items-center rounded-bm bg-accent px-4 text-sm font-medium text-on-accent hover:bg-accent-hover"
          >
            На головну
          </Link>
        }
      />
    </div>
  );
}
