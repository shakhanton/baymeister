import { Button, EmptyState } from '@baymeister/ui';
import { useState } from 'react';
import { Link } from 'react-router';
import { useDismissNeed, useNeeds, useOrderNeed, useSuppliers, type Need } from '../api';
import { ErrorNote, formatQty, ProcurementTabs, STATUS_LABEL, thClass, UNIT_LABEL } from '../components/ui';

export default function NeedsPage() {
  const needs = useNeeds();
  const suppliers = useSuppliers();

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <ProcurementTabs needs={needs.data?.length} />
      <p className="text-sm text-ink-muted">
        Склад повідомляє, коли вільного залишку стає менше за мінімум. Деталь, яку вже купували, сама
        потрапляє в чернетку тому ж постачальнику; для нової — оберіть, у кого замовити.
      </p>

      <ErrorNote message={needs.error?.message} />

      {needs.data && needs.data.length === 0 ? (
        <EmptyState
          title="Усього вистачає"
          description="Мінімальні залишки задаються на картці деталі в розділі «Склад»."
        />
      ) : null}

      {needs.data && needs.data.length > 0 ? (
        <div className="overflow-x-auto rounded-bm border border-line bg-surface">
          <table className="w-full min-w-[860px] border-collapse text-sm">
            <thead>
              <tr className="bg-surface-2">
                {['Деталь', 'Вільно / мінімум', 'Замовлення', ''].map((h) => (
                  <th key={h} className={thClass}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {needs.data.map((n) => (
                <NeedRow key={n.part_id} need={n} suppliers={suppliers.data?.items ?? []} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function NeedRow({ need, suppliers }: { need: Need; suppliers: { id: string; name: string }[] }) {
  const [supplierId, setSupplierId] = useState(need.last_supplier?.id ?? '');
  const order = useOrderNeed();
  const dismiss = useDismissNeed();
  const unit = UNIT_LABEL[need.unit] ?? need.unit;

  return (
    <tr className="border-b border-line align-top last:border-0">
      <td className="px-4 py-3">
        <div className="text-ink">{need.name}</div>
        <div className="font-mono text-xs text-ink-faint">
          {need.brand} {need.sku}
        </div>
      </td>
      <td className="px-4 py-3 tabular">
        <span className={need.free.startsWith('-') ? 'font-medium text-danger' : 'text-ink'}>
          {formatQty(need.free)}
        </span>
        <span className="text-ink-faint">
          {' '}
          / {formatQty(need.min_qty)} {unit}
        </span>
      </td>
      <td className="px-4 py-3">
        {need.order ? (
          <span className="text-ink-muted">
            <Link to={`/procurement/orders/${need.order.id}`} className="font-mono text-accent hover:underline">
              {need.order.number}
            </Link>{' '}
            · {need.order.supplier.name} · {STATUS_LABEL[need.order.status]}
          </span>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <select
                value={supplierId}
                onChange={(e) => setSupplierId(e.target.value)}
                aria-label={`Постачальник: ${need.name}`}
                className="h-8 rounded-bm border border-line-strong bg-surface px-2 text-sm"
              >
                <option value="">— постачальник —</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <Button
                size="sm"
                disabled={!supplierId || order.isPending}
                onClick={() => order.mutate({ partId: need.part_id, supplierId })}
              >
                У чернетку
              </Button>
            </div>
            <ErrorNote message={order.error?.message} />
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        <Button variant="ghost" size="sm" disabled={dismiss.isPending} onClick={() => dismiss.mutate(need.part_id)}>
          Не замовляти
        </Button>
      </td>
    </tr>
  );
}
