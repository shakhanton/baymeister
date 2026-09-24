import { Button, Card, CardBody, CardHeader, CardTitle, EmptyState } from '@baymeister/ui';
import { Link, useSearchParams } from 'react-router';
import { useOrders, type OrderStatus } from '../api';
import { OpenOrderForm } from '../components/open-form';
import { formatMoney, STATUS_LABEL, StatusBadge, thClass } from '../components/ui';

const PAGE_SIZE = 25;

export default function OrdersList() {
  const [params, setParams] = useSearchParams();

  const search = params.get('search') ?? '';
  const status = (params.get('status') as OrderStatus | null) ?? undefined;
  const offset = Number(params.get('offset') ?? 0);
  // ?new=1 — з планувальника: клієнт, авто й запис уже в URL.
  const opening = params.get('new') === '1';

  const query = useOrders({ search: search || undefined, status, limit: PAGE_SIZE, offset });

  function patchParams(next: Record<string, string | null>) {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === '') merged.delete(key);
      else merged.set(key, value);
    }
    if (!('offset' in next)) merged.delete('offset');
    setParams(merged, { replace: true });
  }

  const closeForm = () =>
    patchParams({ new: null, customer: null, vehicle: null, appointment: null });

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => patchParams({ search: e.target.value })}
          placeholder="Номер, держномер або клієнт"
          aria-label="Пошук нарядів"
          className="h-9 w-72 rounded-bm border border-line-strong bg-surface px-3 text-sm placeholder:text-ink-faint"
        />
        <select
          value={status ?? ''}
          onChange={(e) => patchParams({ status: e.target.value || null })}
          aria-label="Статус"
          className="h-9 rounded-bm border border-line-strong bg-surface px-3 text-sm"
        >
          <option value="">Усі статуси</option>
          {Object.entries(STATUS_LABEL).map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
        <Button className="ml-auto" onClick={() => (opening ? closeForm() : patchParams({ new: '1' }))}>
          {opening ? 'Згорнути' : 'Новий наряд'}
        </Button>
      </div>

      {opening ? (
        <Card>
          <CardHeader>
            <CardTitle>Новий наряд</CardTitle>
          </CardHeader>
          <CardBody>
            <OpenOrderForm
              initial={{
                customerId: params.get('customer'),
                vehicleId: params.get('vehicle'),
                appointmentId: params.get('appointment'),
              }}
              onCancel={closeForm}
            />
          </CardBody>
        </Card>
      ) : null}

      {query.isError ? (
        <p role="alert" className="rounded-bm bg-danger-soft px-4 py-3 text-sm text-danger">
          {query.error.message}
        </p>
      ) : null}

      {query.data && query.data.items.length === 0 ? (
        <EmptyState
          title={search || status ? 'Нічого не знайдено' : 'Нарядів ще немає'}
          description={
            search || status
              ? 'Спробуйте інший запит або очистіть фільтри.'
              : 'Відкрийте наряд тут або з планувальника, коли клієнт приїхав.'
          }
        />
      ) : null}

      {query.data && query.data.items.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-bm border border-line bg-surface">
            <table className="w-full min-w-[820px] border-collapse text-sm">
              <thead>
                <tr className="bg-surface-2">
                  {['Наряд', 'Автомобіль', 'Клієнт', 'Статус', 'Сума'].map((h) => (
                    <th key={h} className={thClass}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((order) => (
                  <tr key={order.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        to={`/work-orders/${order.id}`}
                        className="font-mono font-medium text-accent hover:underline"
                      >
                        {order.number}
                      </Link>
                      <div className="text-xs text-ink-faint">
                        {new Date(order.opened_at).toLocaleDateString('uk-UA')}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-ink">{order.vehicle_label}</td>
                    <td className="px-4 py-3">
                      <div className="text-ink">{order.customer_name}</div>
                      <div className="font-mono text-xs text-ink-muted">{order.customer_phone}</div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={order.status} />
                    </td>
                    <td className="px-4 py-3 text-right tabular font-medium text-ink">
                      {formatMoney(order.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-ink-faint">
            Показано {query.data.items.length} з {query.data.total}
            {query.data.total > PAGE_SIZE ? (
              <>
                {' · '}
                <button
                  type="button"
                  className="text-accent underline underline-offset-2 disabled:opacity-40"
                  disabled={offset === 0}
                  onClick={() => patchParams({ offset: String(Math.max(0, offset - PAGE_SIZE)) })}
                >
                  назад
                </button>
                {' · '}
                <button
                  type="button"
                  className="text-accent underline underline-offset-2 disabled:opacity-40"
                  disabled={offset + PAGE_SIZE >= query.data.total}
                  onClick={() => patchParams({ offset: String(offset + PAGE_SIZE) })}
                >
                  далі
                </button>
              </>
            ) : null}
          </p>
        </>
      ) : null}
    </div>
  );
}
