import { Button, Card, CardBody, CardHeader, CardTitle, EmptyState } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { useCreateOrder, useNeeds, useOrders, useSuppliers, type OrderStatus } from '../api';
import {
  ErrorNote,
  formatDate,
  formatMoney,
  inputClass,
  ProcurementTabs,
  STATUS_LABEL,
  StatusBadge,
  thClass,
} from '../components/ui';

const FILTERS: (OrderStatus | null)[] = [null, 'draft', 'ordered', 'received', 'cancelled'];

export default function OrdersPage() {
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const search = params.get('search') ?? '';
  const status = (params.get('status') as OrderStatus | null) ?? null;
  const query = useOrders(search, status);
  const needs = useNeeds();

  function patchParams(next: Record<string, string | null>) {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === '') merged.delete(key);
      else merged.set(key, value);
    }
    setParams(merged, { replace: true });
  }

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <ProcurementTabs needs={needs.data?.length} />

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => patchParams({ search: e.target.value })}
          placeholder="Номер або постачальник"
          aria-label="Пошук замовлень"
          className="h-9 w-72 rounded-bm border border-line-strong bg-surface px-3 text-sm placeholder:text-ink-faint"
        />
        <div className="flex gap-1" role="group" aria-label="Статус">
          {FILTERS.map((f) => (
            <Button
              key={f ?? 'all'}
              size="sm"
              variant={status === f ? 'primary' : 'ghost'}
              onClick={() => patchParams({ status: f })}
            >
              {f ? STATUS_LABEL[f] : 'усі'}
            </Button>
          ))}
        </div>
        <Button className="ml-auto" onClick={() => setCreating((v) => !v)}>
          {creating ? 'Згорнути' : 'Нове замовлення'}
        </Button>
      </div>

      {creating ? <NewOrder onCancel={() => setCreating(false)} /> : null}

      <ErrorNote message={query.error?.message} />

      {query.data && query.data.items.length === 0 ? (
        <EmptyState
          title={search || status ? 'Нічого не знайдено' : 'Замовлень ще немає'}
          description={
            search || status
              ? 'Спробуйте інший запит або зніміть фільтр.'
              : 'Створіть замовлення постачальнику — або дочекайтесь, поки склад попросить деталей.'
          }
        />
      ) : null}

      {query.data && query.data.items.length > 0 ? (
        <div className="overflow-x-auto rounded-bm border border-line bg-surface">
          <table className="w-full min-w-[860px] border-collapse text-sm">
            <thead>
              <tr className="bg-surface-2">
                {['Номер', 'Постачальник', 'Статус', 'Рядків', 'Отримано', 'Очікується', 'Сума'].map((h) => (
                  <th key={h} className={thClass}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((o) => (
                <tr key={o.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3">
                    <Link to={`/procurement/orders/${o.id}`} className="font-mono font-medium text-accent hover:underline">
                      {o.number}
                    </Link>
                    {o.auto ? <div className="text-xs text-ink-faint">склав сервіс</div> : null}
                  </td>
                  <td className="px-4 py-3 text-ink">{o.supplier.name}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={o.status} />
                  </td>
                  <td className="px-4 py-3 tabular text-ink-muted">{o.lines}</td>
                  <td className="px-4 py-3 tabular text-ink-muted">
                    {o.status === 'ordered' || o.status === 'received'
                      ? `${Math.round(o.received_share * 100)} %`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 tabular text-ink-muted">{formatDate(o.expected_on)}</td>
                  <td className="px-4 py-3 tabular font-medium text-ink">{formatMoney(o.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function NewOrder({ onCancel }: { onCancel: () => void }) {
  const suppliers = useSuppliers();
  const create = useCreateOrder();
  const navigate = useNavigate();
  const [supplierId, setSupplierId] = useState('');
  const [expected, setExpected] = useState('');

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    create.mutate(
      { supplier_id: supplierId, expected_on: expected || null },
      { onSuccess: (order) => navigate(`/procurement/orders/${order.id}`) },
    );
  }

  const list = suppliers.data?.items ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Нове замовлення</CardTitle>
      </CardHeader>
      <CardBody>
        {suppliers.data && list.length === 0 ? (
          <p className="text-sm text-ink-muted">
            Спершу{' '}
            <Link to="/procurement/suppliers" className="text-accent underline underline-offset-2">
              додайте постачальника
            </Link>
            .
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-64 flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Постачальник</span>
              <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} className={inputClass}>
                <option value="">— оберіть —</option>
                {list.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Очікується</span>
              <input type="date" value={expected} onChange={(e) => setExpected(e.target.value)} className={inputClass} />
            </label>
            <Button type="submit" disabled={!supplierId || create.isPending}>
              Створити чернетку
            </Button>
            <Button type="button" variant="ghost" onClick={onCancel}>
              Скасувати
            </Button>
          </form>
        )}
        <div className="mt-3">
          <ErrorNote message={create.error?.message} />
        </div>
      </CardBody>
    </Card>
  );
}
