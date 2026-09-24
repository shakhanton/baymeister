import { Button, Card, CardBody, CardHeader, CardTitle } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import {
  useAddLine,
  useCatalogSearch,
  useChangeStatus,
  useOrder,
  useRemoveLine,
  useUpdateLine,
  type Line,
  type Order,
  type OrderStatus,
} from '../api';
import {
  ErrorNote,
  formatMoney,
  formatQty,
  inputClass,
  StatusBadge,
  thClass,
  UNIT_LABEL,
} from '../components/ui';

/** Ті самі переходи, що дозволяє бекенд. Кнопок недозволених просто немає. */
const ACTIONS: Record<OrderStatus, { to: OrderStatus; label: string; primary?: boolean }[]> = {
  open: [
    { to: 'in_progress', label: 'В роботу', primary: true },
    { to: 'cancelled', label: 'Скасувати' },
  ],
  in_progress: [
    { to: 'done', label: 'Роботи завершено', primary: true },
    { to: 'cancelled', label: 'Скасувати' },
  ],
  done: [
    { to: 'closed', label: 'Видати й закрити', primary: true },
    { to: 'in_progress', label: 'Повернути в роботу' },
  ],
  closed: [],
  cancelled: [],
};

const EDITABLE: OrderStatus[] = ['open', 'in_progress'];

export default function OrderDetail() {
  const { orderId = '' } = useParams();
  const query = useOrder(orderId);
  const change = useChangeStatus(orderId);

  if (query.isPending) {
    return <div className="h-40 max-w-5xl animate-pulse rounded-bm bg-surface-2" role="status" />;
  }
  if (query.isError) {
    return (
      <div className="flex max-w-5xl flex-col gap-3">
        <ErrorNote message={query.error.message} />
        <Link to="/work-orders" className="text-sm text-accent underline underline-offset-2">
          ← До нарядів
        </Link>
      </div>
    );
  }

  const order = query.data;
  const editable = EDITABLE.includes(order.status);

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <Link to="/work-orders" className="text-sm text-accent underline underline-offset-2">
        ← До нарядів
      </Link>

      <Card>
        <CardHeader className="flex flex-wrap items-center gap-3">
          <CardTitle className="font-mono">Наряд {order.number}</CardTitle>
          <StatusBadge status={order.status} />
          <div className="ml-auto flex flex-wrap gap-2">
            {ACTIONS[order.status].map((a) => (
              <Button
                key={a.to}
                size="sm"
                variant={a.primary ? 'primary' : 'outline'}
                disabled={change.isPending}
                onClick={() => change.mutate(a.to)}
              >
                {a.label}
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardBody className="flex flex-col gap-4">
          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-3">
            <Row label="Клієнт" value={`${order.customer_name} · ${order.customer_phone}`} />
            <Row label="Автомобіль" value={order.vehicle_label} />
            <Row
              label="Пробіг"
              value={order.mileage_km != null ? `${order.mileage_km.toLocaleString('uk-UA')} км` : null}
            />
            <Row label="Скарга" value={order.complaint} className="sm:col-span-3" />
          </dl>
          <ErrorNote message={change.error?.message} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Роботи й запчастини</CardTitle>
        </CardHeader>
        <CardBody className="flex flex-col gap-4">
          <LinesTable order={order} editable={editable} />
          {editable ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <AddLine orderId={order.id} kind="service" />
              <AddLine orderId={order.id} kind="part" />
            </div>
          ) : (
            <p className="text-xs text-ink-faint">
              Наряд у статусі «{order.status === 'done' ? 'роботи завершено' : 'закрито'}» — рядки
              не змінюються.
            </p>
          )}
          <TotalsBlock order={order} />
        </CardBody>
      </Card>
    </div>
  );
}

function LinesTable({ order, editable }: { order: Order; editable: boolean }) {
  const update = useUpdateLine(order.id);
  const remove = useRemoveLine(order.id);

  if (order.lines.length === 0) {
    return <p className="text-sm text-ink-muted">Порожньо. Додайте роботи й запчастини нижче.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto rounded-bm border border-line">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="bg-surface-2">
              {['Позиція', 'К-сть', 'Ціна', 'Сума', ''].map((h) => (
                <th key={h} className={thClass}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {order.lines.map((line) => (
              <LineRow
                key={line.id}
                line={line}
                editable={editable}
                pending={update.isPending || remove.isPending}
                onQty={(qty) => update.mutate({ lineId: line.id, qty })}
                onRemove={() => remove.mutate(line.id)}
              />
            ))}
          </tbody>
        </table>
      </div>
      <ErrorNote message={update.error?.message ?? remove.error?.message} />
    </div>
  );
}

function LineRow({
  line,
  editable,
  pending,
  onQty,
  onRemove,
}: {
  line: Line;
  editable: boolean;
  pending: boolean;
  onQty: (qty: string) => void;
  onRemove: () => void;
}) {
  const [qty, setQty] = useState(formatQty(line.qty));
  const changed = qty.replace(',', '.') !== formatQty(line.qty).replace(',', '.');

  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-4 py-2">
        <div className="text-ink">{line.name}</div>
        <div className="font-mono text-xs text-ink-faint">
          {line.kind === 'service' ? 'робота' : 'запчастина'} · {line.code}
        </div>
      </td>
      <td className="px-4 py-2">
        {editable ? (
          <form
            className="flex items-center gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              if (changed) onQty(qty);
            }}
          >
            <input
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              inputMode="decimal"
              aria-label={`Кількість: ${line.name}`}
              className="h-8 w-20 rounded-bm border border-line-strong bg-surface px-2 text-sm tabular"
            />
            <span className="text-xs text-ink-faint">{UNIT_LABEL[line.unit] ?? line.unit}</span>
            {changed ? (
              <Button type="submit" size="sm" variant="outline" disabled={pending}>
                OK
              </Button>
            ) : null}
          </form>
        ) : (
          <span className="tabular text-ink">
            {formatQty(line.qty)} {UNIT_LABEL[line.unit] ?? line.unit}
          </span>
        )}
      </td>
      <td className="px-4 py-2 tabular text-ink-muted">{formatMoney(line.unit_price)}</td>
      <td className="px-4 py-2 tabular font-medium text-ink">{formatMoney(line.amount)}</td>
      <td className="px-4 py-2 text-right">
        {editable ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={pending}
            onClick={onRemove}
            aria-label={`Прибрати: ${line.name}`}
          >
            Прибрати
          </Button>
        ) : null}
      </td>
    </tr>
  );
}

/** Пошук по прайсу. Ціна фіксується бекендом у момент додавання. */
function AddLine({ orderId, kind }: { orderId: string; kind: 'service' | 'part' }) {
  const [search, setSearch] = useState('');
  const results = useCatalogSearch(kind, search);
  const add = useAddLine(orderId);
  const title = kind === 'service' ? 'Додати роботу' : 'Додати запчастину';

  function pick(event: FormEvent, catalogId: string) {
    event.preventDefault();
    add.mutate({ kind, catalog_id: catalogId }, { onSuccess: () => setSearch('') });
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">{title}</span>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={kind === 'service' ? 'Код або назва роботи' : 'Артикул, назва або бренд'}
          className={inputClass}
        />
      </label>
      {search.trim() ? (
        <ul className="overflow-hidden rounded-bm border border-line bg-surface" role="listbox" aria-label={title}>
          {results.data?.length === 0 ? (
            <li className="px-3 py-2 text-sm text-ink-muted">Нічого в прайсі</li>
          ) : null}
          {results.data?.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                role="option"
                aria-selected="false"
                disabled={add.isPending}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface-2"
                onClick={(e) => pick(e, item.id)}
              >
                <span className="font-mono text-xs text-ink-faint">{item.code}</span>
                <span className="text-ink">{item.name}</span>
                <span className="ml-auto tabular text-ink-muted">{formatMoney(item.price)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <ErrorNote message={add.error?.message} />
    </div>
  );
}

function TotalsBlock({ order }: { order: Order }) {
  const t = order.totals;
  const hasDiscount = t.discount !== '0.00';
  return (
    <dl className="ml-auto grid w-full max-w-xs grid-cols-[1fr_auto] gap-x-6 gap-y-1 text-sm">
      <dt className="text-ink-muted">Роботи</dt>
      <dd className="text-right tabular text-ink">{formatMoney(t.services)}</dd>
      <dt className="text-ink-muted">Запчастини</dt>
      <dd className="text-right tabular text-ink">{formatMoney(t.parts)}</dd>
      {hasDiscount ? (
        <>
          <dt className="text-ink-muted">Знижка {t.discount_percent.replace('.00', '')} %</dt>
          <dd className="text-right tabular text-ink">−{formatMoney(t.discount)}</dd>
        </>
      ) : null}
      <dt className="mt-2 border-t border-line pt-2 font-medium text-ink">До сплати</dt>
      <dd className="mt-2 border-t border-line pt-2 text-right font-cond text-xl font-bold tabular text-ink">
        {formatMoney(t.total)}
      </dd>
    </dl>
  );
}

function Row({
  label,
  value,
  className,
}: {
  label: string;
  value: string | null | undefined;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="font-mono text-[11px] tracking-wider text-ink-faint uppercase">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{value || '—'}</dd>
    </div>
  );
}
