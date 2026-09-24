import { Badge, Button, Card, CardBody, CardHeader, CardTitle } from '@baymeister/ui';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useRoles, useSetUserActive, useUpdateUser, useUser, type UserUpdate } from '../api';
import { UserForm, type UserFormValues } from '../components/user-form';

export default function UserDetail() {
  const { userId = '' } = useParams();
  const [editing, setEditing] = useState(false);

  const query = useUser(userId);
  const roles = useRoles();
  const update = useUpdateUser(userId);
  const setActive = useSetUserActive(userId);

  if (query.isPending) {
    return <div className="h-40 max-w-3xl animate-pulse rounded-bm bg-surface-2" role="status" />;
  }

  if (query.isError) {
    return (
      <div className="flex max-w-3xl flex-col gap-3">
        <p role="alert" className="rounded-bm bg-danger-soft px-4 py-3 text-sm text-danger">
          {query.error.message}
        </p>
        <Link to="/users" className="text-sm text-accent underline underline-offset-2">
          ← До списку співробітників
        </Link>
      </div>
    );
  }

  const user = query.data;
  const role = roles.data?.find((r) => r.id === user.role);

  function handleSave(values: UserFormValues) {
    const body: UserUpdate = { email: values.email, name: values.name, role: values.role };
    if (values.password) body.password = values.password;
    // Помилку показує форма через update.error — тут її не ловимо.
    update.mutate(body, { onSuccess: () => setEditing(false) });
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <Link to="/users" className="text-sm text-accent underline underline-offset-2">
        ← До списку співробітників
      </Link>

      <Card>
        <CardHeader className="flex flex-wrap items-center gap-3">
          <CardTitle>{user.name}</CardTitle>
          <Badge tone={user.role === 'owner' ? 'accent' : 'neutral'}>
            {role?.title ?? user.role}
          </Badge>
          {!user.is_active ? <Badge tone="planned">вимкнений</Badge> : null}

          <div className="ml-auto flex gap-2">
            {user.is_active ? (
              <Button variant="outline" size="sm" onClick={() => setEditing((v) => !v)}>
                {editing ? 'Скасувати' : 'Редагувати'}
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              disabled={setActive.isPending}
              onClick={() => setActive.mutate(!user.is_active)}
            >
              {user.is_active ? 'Вимкнути' : 'Увімкнути'}
            </Button>
          </div>
        </CardHeader>

        <CardBody>
          {editing ? (
            <UserForm
              mode="edit"
              defaultValues={user}
              submitLabel="Зберегти"
              pending={update.isPending}
              error={update.error?.message ?? null}
              onSubmit={handleSave}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
              <Row label="Email" value={user.email} mono />
              <Row
                label="Останній вхід"
                value={
                  user.last_login_at
                    ? new Date(user.last_login_at).toLocaleString('uk-UA')
                    : null
                }
              />
              <Row
                label="Права ролі"
                value={role ? formatPermissions(role.permissions) : null}
                mono
                className="sm:col-span-2"
              />
            </dl>
          )}

          {setActive.isError ? (
            <p role="alert" className="mt-4 rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
              {setActive.error.message}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <p className="text-xs text-ink-faint">
        Зміна ролі діє з наступного входу співробітника — поточна сесія живе до кінця зміни.
      </p>
    </div>
  );
}

function formatPermissions(permissions: string[]): string {
  return permissions.includes('*') ? 'повний доступ' : permissions.join(', ');
}

function Row({
  label,
  value,
  mono,
  className,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="font-mono text-[11px] tracking-wider text-ink-faint uppercase">{label}</dt>
      <dd className={`mt-0.5 text-sm text-ink ${mono ? 'font-mono' : ''}`}>{value || '—'}</dd>
    </div>
  );
}
