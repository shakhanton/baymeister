import { Badge, Button, Card, CardBody, CardHeader, CardTitle, EmptyState } from '@baymeister/ui';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useCreateCustomer, useCustomers, type CustomerType } from '../api';
import { CustomerForm, type CustomerFormValues } from '../components/customer-form';

const PAGE_SIZE = 25;

export default function CustomersList() {
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);

  const search = params.get('search') ?? '';
  const type = (params.get('type') as CustomerType | null) ?? undefined;
  const archived = params.get('archived') === '1';
  const offset = Number(params.get('offset') ?? 0);

  const query = useCustomers({ search: search || undefined, type, archived, limit: PAGE_SIZE, offset });
  const create = useCreateCustomer();

  function patchParams(next: Record<string, string | null>) {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === '') merged.delete(key);
      else merged.set(key, value);
    }
    if (!('offset' in next)) merged.delete('offset');
    setParams(merged, { replace: true });
  }

  async function handleCreate(values: CustomerFormValues) {
    await create.mutateAsync({
      type: values.type,
      name: values.name,
      phone: values.phone,
      email: values.email || null,
      tax_id: values.tax_id || null,
      notes: values.notes || null,
      discount_percent: values.discount_percent,
    });
    setCreating(false);
  }

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => patchParams({ search: e.target.value })}
          placeholder="Імʼя, телефон або код"
          aria-label="Пошук клієнтів"
          className="h-9 w-64 rounded-bm border border-line-strong bg-surface px-3 text-sm placeholder:text-ink-faint"
        />

        <select
          value={type ?? ''}
          onChange={(e) => patchParams({ type: e.target.value || null })}
          aria-label="Тип клієнта"
          className="h-9 rounded-bm border border-line-strong bg-surface px-3 text-sm"
        >
          <option value="">Усі типи</option>
          <option value="individual">Фізичні особи</option>
          <option value="company">Юридичні особи</option>
        </select>

        <label className="flex items-center gap-2 text-sm text-ink-muted">
          <input
            type="checkbox"
            checked={archived}
            onChange={(e) => patchParams({ archived: e.target.checked ? '1' : null })}
          />
          Архів
        </label>

        <Button className="ml-auto" onClick={() => setCreating((v) => !v)}>
          {creating ? 'Згорнути' : 'Додати клієнта'}
        </Button>
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Новий клієнт</CardTitle>
          </CardHeader>
          <CardBody>
            <CustomerForm
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
          title={search ? 'Нічого не знайдено' : archived ? 'Архів порожній' : 'Клієнтів ще немає'}
          description={
            search
              ? 'Спробуйте інший запит або очистіть фільтри.'
              : 'Перший клієнт зʼявиться тут одразу після створення.'
          }
        />
      ) : null}

      {query.data && query.data.items.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-bm border border-line bg-surface">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="bg-surface-2">
                  {['Клієнт', 'Телефон', 'Код', 'Знижка'].map((h) => (
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
                {query.data.items.map((customer) => (
                  <tr key={customer.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        to={`/customers/${customer.id}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {customer.name}
                      </Link>
                      <div className="mt-0.5">
                        <Badge tone={customer.type === 'company' ? 'accent' : 'neutral'}>
                          {customer.type === 'company' ? 'юр. особа' : 'фіз. особа'}
                        </Badge>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-ink-muted">{customer.phone}</td>
                    <td className="px-4 py-3 font-mono text-ink-muted">{customer.tax_id ?? '—'}</td>
                    <td className="px-4 py-3 tabular text-ink-muted">
                      {customer.discount_percent > 0 ? `${customer.discount_percent}%` : '—'}
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
