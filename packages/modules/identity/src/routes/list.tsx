import { Badge, Button, Card, CardBody, CardHeader, CardTitle, EmptyState } from '@baymeister/ui';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useCreateUser, useRoles, useUsers } from '../api';
import { UserForm, type UserFormValues } from '../components/user-form';

const PAGE_SIZE = 25;

export default function UsersList() {
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);

  const search = params.get('search') ?? '';
  const inactive = params.get('inactive') === '1';
  const offset = Number(params.get('offset') ?? 0);

  const query = useUsers({ search: search || undefined, inactive, limit: PAGE_SIZE, offset });
  const roles = useRoles();
  const create = useCreateUser();

  const roleTitle = new Map(roles.data?.map((r) => [r.id, r.title]));

  function patchParams(next: Record<string, string | null>) {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === '') merged.delete(key);
      else merged.set(key, value);
    }
    if (!('offset' in next)) merged.delete('offset');
    setParams(merged, { replace: true });
  }

  function handleCreate(values: UserFormValues) {
    // Помилку показує форма через create.error — тут її не ловимо.
    create.mutate(values, { onSuccess: () => setCreating(false) });
  }

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => patchParams({ search: e.target.value })}
          placeholder="Імʼя або email"
          aria-label="Пошук співробітників"
          className="h-9 w-64 rounded-bm border border-line-strong bg-surface px-3 text-sm placeholder:text-ink-faint"
        />

        <label className="flex items-center gap-2 text-sm text-ink-muted">
          <input
            type="checkbox"
            checked={inactive}
            onChange={(e) => patchParams({ inactive: e.target.checked ? '1' : null })}
          />
          Вимкнені
        </label>

        <Button className="ml-auto" onClick={() => setCreating((v) => !v)}>
          {creating ? 'Згорнути' : 'Додати співробітника'}
        </Button>
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Новий співробітник</CardTitle>
          </CardHeader>
          <CardBody>
            <UserForm
              mode="create"
              submitLabel="Створити"
              pending={create.isPending}
              error={create.error?.message ?? null}
              onSubmit={handleCreate}
              onCancel={() => setCreating(false)}
            />
          </CardBody>
        </Card>
      ) : null}

      {query.isPending ? <ListSkeleton /> : null}

      {query.isError ? (
        <p role="alert" className="rounded-bm bg-danger-soft px-4 py-3 text-sm text-danger">
          {query.error.message}
        </p>
      ) : null}

      {query.data && query.data.items.length === 0 ? (
        <EmptyState
          title={search ? 'Нічого не знайдено' : inactive ? 'Вимкнених немає' : 'Співробітників ще немає'}
          description={
            search
              ? 'Спробуйте інший запит або очистіть фільтри.'
              : 'Новий співробітник зʼявиться тут одразу після створення.'
          }
        />
      ) : null}

      {query.data && query.data.items.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-bm border border-line bg-surface">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="bg-surface-2">
                  {['Співробітник', 'Email', 'Роль', 'Останній вхід'].map((h) => (
                    <th
                      key={h}
                      className="border-b border-line-strong px-4 py-3 text-left font-mono text-[11px] font-medium tracking-wider text-ink-faint uppercase"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((user) => (
                  <tr key={user.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        to={`/users/${user.id}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {user.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-ink-muted">{user.email}</td>
                    <td className="px-4 py-3">
                      <Badge tone={user.role === 'owner' ? 'accent' : 'neutral'}>
                        {roleTitle.get(user.role) ?? user.role}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 tabular text-ink-muted">
                      {user.last_login_at ? formatDate(user.last_login_at) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            total={query.data.total}
            offset={offset}
            onChange={(next) => patchParams({ offset: String(next) })}
          />
        </>
      ) : null}
    </div>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('uk-UA', { dateStyle: 'short', timeStyle: 'short' });
}

function Pagination({
  total,
  offset,
  onChange,
}: {
  total: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  if (total <= PAGE_SIZE) {
    return <p className="text-xs text-ink-faint">Усього: {total}</p>;
  }

  const from = offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="tabular text-ink-muted">
        {from}–{to} з {total}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - PAGE_SIZE))}
      >
        Назад
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={to >= total}
        onClick={() => onChange(offset + PAGE_SIZE)}
      >
        Далі
      </Button>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-2" role="status" aria-label="Завантаження">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="h-12 animate-pulse rounded-bm bg-surface-2" />
      ))}
    </div>
  );
}
