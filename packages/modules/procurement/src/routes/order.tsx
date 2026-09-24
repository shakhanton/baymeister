import { Button, Card, CardBody, CardHeader, CardTitle } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import {
  useAddLine,
  useChangeStatus,
  useOrder,
  usePartSearch,
  useReceive,
  useRemoveLine,
  useUpdateLine,
  type Line,
  type Order,
} from '../api';
import {
  ErrorNote,
  formatDate,
  formatMoney,
  formatQty,
  inputClass,
  MONEY_RE,
  QTY_RE,
  StatusBadge,
  thClass,
  UNIT_LABEL,
} from '../components/ui';

const cellInput = 'h-8 rounded-bm border border-line-strong bg-surface px-2 text-sm tabular';

/** «175.50» → «175,5» — для поля вводу. */
function editable(value: string): string {
  return formatQty(value);
}

export default function OrderPage() {
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
        <Link to="/procurement" className="text-sm text-accent underline underline-offset-2">
          ← До замовлень
        </Link>
      </div>
    );
  }

  const order = query.data;
  const draft = order.status === 'draft';
  const received = order.receipts.length > 0;

  // Ті самі переходи, що дозволяє бекенд. Недозволених кнопок просто немає.
  const actions: { to: 'ordered' | 'received' | 'cancelled'; label: string; primary?: boolean }[] = [];
  if (draft) {
    actions.push({ to: 'ordered', label: 'Відправлено постачальнику', primary: true });
    actions.push({ to: 'cancelled', label: 'Скасувати' });
  } else if (order.status === 'ordered') {
    if (received) actions.push({ to: 'received', label: 'Закрити з недопоставкою' });
    else actions.push({ to: 'cancelled', label: 'Скасувати' });
  }

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <Link to="/procurement" className="text-sm text-accent underline underline-offset-2">
        ← До замовлень
      </Link>

      <Card>
        <CardHeader className="flex flex-wrap items-center gap-3">
          <CardTitle className="font-mono">Замовлення {order.number}</CardTitle>
          <StatusBadge status={order.status} />
          <div className="ml-auto flex flex-wrap gap-2">
            {actions.map((a) => (
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
          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-4">
            <Row label="Постачальник" value={order.supplier.name} />
            <Row label="Створено" value={formatDate(order.created_at)} />
            <Row label="Відправлено" value={formatDate(order.ordered_at)} />
            <Row label="Очікується" value={formatDate(order.expected_on)} />
            {order.note ? <Row label="Примітка" value={order.note} className="sm:col-span-4" /> : null}
          </dl>
          <ErrorNote message={change.error?.message} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Деталі</CardTitle>
        </CardHeader>
        <CardBody className="flex flex-col gap-4">
          <LinesTable order={order} />
          {draft ? (
            <AddLine orderId={order.id} />
          ) : (
            <p className="text-xs text-ink-faint">
              Замовлення вже не чернетка — рядки не змінюються.
            </p>
          )}
          <div className="ml-auto flex items-baseline gap-6 text-sm">
            <span className="text-ink-muted">Разом</span>
            <span className="font-cond text-xl font-bold tabular text-ink">{formatMoney(order.total)}</span>
          </div>
        </CardBody>
      </Card>

      {order.status === 'ordered' ? <ReceiveForm key={order.receipts.length} order={order} /> : null}

      {received ? (
        <Card>
          <CardHeader>
            <CardTitle>Приходи</CardTitle>
          </CardHeader>
          <CardBody>
            <table className="w-full border-collapse text-sm">
              <tbody>
                {order.receipts.map((r) => (
                  <tr key={r.id} className="border-b border-line last:border-0">
                    <td className="py-2 pr-4 tabular text-ink-muted">
                      {new Date(r.received_at).toLocaleString('uk-UA', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    <td className="py-2 pr-4 text-ink">
                      {r.invoice_number ? `накладна ${r.invoice_number}` : 'без накладної'}
                    </td>
                    <td className="py-2 pr-4 text-ink-muted">рядків: {r.lines}</td>
                    <td className="py-2 text-right tabular font-medium text-ink">{formatMoney(r.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-ink-faint">Кожен прихід стає партією на складі за ціною з накладної.</p>
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}

function LinesTable({ order }: { order: Order }) {
  const update = useUpdateLine(order.id);
  const remove = useRemoveLine(order.id);
  const draft = order.status === 'draft';

  if (order.lines.length === 0) {
    return <p className="text-sm text-ink-muted">Порожньо. Додайте деталі з прайсу нижче.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto rounded-bm border border-line">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="bg-surface-2">
              {['Деталь', 'К-сть', 'Ціна', 'Сума', 'Отримано', ''].map((h) => (
                <th key={h} className={thClass}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {order.lines.map((line) => (
              <LineRow
                key={`${line.id}:${line.qty}:${line.unit_cost}`}
                line={line}
                draft={draft}
                pending={update.isPending || remove.isPending}
                onSave={(body) => update.mutate({ lineId: line.id, ...body })}
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
  draft,
  pending,
  onSave,
  onRemove,
}: {
  line: Line;
  draft: boolean;
  pending: boolean;
  onSave: (body: { qty?: string; unit_cost?: string }) => void;
  onRemove: () => void;
}) {
  const [qty, setQty] = useState(editable(line.qty));
  const [cost, setCost] = useState(editable(line.unit_cost));
  const qtyChanged = qty !== editable(line.qty);
  const costChanged = cost !== editable(line.unit_cost);
  const valid = QTY_RE.test(qty.trim()) && MONEY_RE.test(cost.trim());
  const unit = UNIT_LABEL[line.unit] ?? line.unit;
  const done = Number(line.qty_received) >= Number(line.qty);

  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-4 py-2">
        <div className="text-ink">{line.name}</div>
        <div className="font-mono text-xs text-ink-faint">
          {line.brand} {line.sku}
        </div>
      </td>
      {draft ? (
        <td className="px-4 py-2" colSpan={2}>
          <form
            className="flex items-center gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              onSave({ ...(qtyChanged ? { qty } : {}), ...(costChanged ? { unit_cost: cost } : {}) });
            }}
          >
            <input
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              inputMode="decimal"
              aria-label={`Кількість: ${line.name}`}
              className={`${cellInput} w-20`}
            />
            <span className="w-10 text-xs text-ink-faint">{unit}</span>
            <input
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              inputMode="decimal"
              aria-label={`Ціна: ${line.name}`}
              className={`${cellInput} w-24 ${line.unit_cost === '0.00' ? 'border-danger' : ''}`}
            />
            <span className="text-xs text-ink-faint">₴</span>
            {qtyChanged || costChanged ? (
              <Button type="submit" size="sm" variant="outline" disabled={pending || !valid}>
                OK
              </Button>
            ) : null}
          </form>
        </td>
      ) : (
        <>
          <td className="px-4 py-2 tabular text-ink">
            {formatQty(line.qty)} {unit}
          </td>
          <td className="px-4 py-2 tabular text-ink-muted">{formatMoney(line.unit_cost)}</td>
        </>
      )}
      <td className="px-4 py-2 tabular font-medium text-ink">{formatMoney(line.amount)}</td>
      <td className={`px-4 py-2 tabular ${done ? 'text-ready' : 'text-ink-muted'}`}>
        {formatQty(line.qty_received)} / {formatQty(line.qty)}
      </td>
      <td className="px-4 py-2 text-right">
        {draft ? (
          <Button variant="ghost" size="sm" disabled={pending} onClick={onRemove} aria-label={`Прибрати: ${line.name}`}>
            Прибрати
          </Button>
        ) : null}
      </td>
    </tr>
  );
}

function AddLine({ orderId }: { orderId: string }) {
  const [search, setSearch] = useState('');
  const [part, setPart] = useState<{ id: string; label: string } | null>(null);
  const [qty, setQty] = useState('');
  const [cost, setCost] = useState('');
  const results = usePartSearch(search);
  const add = useAddLine(orderId);
  const valid = part !== null && QTY_RE.test(qty.trim()) && MONEY_RE.test(cost.trim());

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!part) return;
    add.mutate(
      { part_id: part.id, qty: qty.trim(), unit_cost: cost.trim() },
      {
        onSuccess: () => {
          setPart(null);
          setSearch('');
          setQty('');
          setCost('');
        },
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 border-t border-line pt-4 sm:grid-cols-4" noValidate>
      {part ? (
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <span className="text-sm font-medium text-ink">Деталь</span>
          <div className="flex h-9 items-center gap-2 rounded-bm border border-line-strong px-3 text-sm">
            <span className="truncate text-ink">{part.label}</span>
            <Button type="button" variant="ghost" size="sm" className="ml-auto" onClick={() => setPart(null)}>
              Змінити
            </Button>
          </div>
        </div>
      ) : (
        <label className="relative flex flex-col gap-1.5 sm:col-span-2">
          <span className="text-sm font-medium text-ink">Додати деталь з прайсу</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Артикул, назва або бренд"
            className={inputClass}
          />
          {search.trim() ? (
            <ul className="overflow-hidden rounded-bm border border-line bg-surface" role="listbox" aria-label="Деталі з прайсу">
              {results.data?.length === 0 ? (
                <li className="px-3 py-2 text-sm text-ink-muted">Нічого в прайсі</li>
              ) : null}
              {results.data?.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected="false"
                    className="flex w-full gap-2 px-3 py-2 text-left text-sm hover:bg-surface-2"
                    onClick={() => setPart({ id: p.id, label: `${p.name} · ${p.brand} ${p.sku}` })}
                  >
                    <span className="font-mono text-xs text-ink-faint">
                      {p.brand} {p.sku}
                    </span>
                    <span className="text-ink">{p.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </label>
      )}
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">Кількість</span>
        <input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal" className={`${inputClass} tabular`} />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">Закупівельна ціна, ₴</span>
        <input value={cost} onChange={(e) => setCost(e.target.value)} inputMode="decimal" className={`${inputClass} tabular`} />
      </label>
      <div className="flex flex-col gap-2 sm:col-span-4">
        <ErrorNote message={add.error?.message} />
        <div>
          <Button type="submit" variant="outline" size="sm" disabled={!valid || add.isPending}>
            Додати в замовлення
          </Button>
        </div>
      </div>
    </form>
  );
}

/** Прихід за накладною: скільки приїхало по кожному рядку. За замовчуванням — усе, що лишилось. */
function ReceiveForm({ order }: { order: Order }) {
  const open = order.lines.filter((l) => Number(l.qty_received) < Number(l.qty));
  const remaining = (l: Line) => formatQty((Number(l.qty) - Number(l.qty_received)).toFixed(3));
  const [invoice, setInvoice] = useState('');
  const [qty, setQty] = useState<Record<string, string>>(() =>
    Object.fromEntries(open.map((l) => [l.id, remaining(l)])),
  );
  const [cost, setCost] = useState<Record<string, string>>(() =>
    Object.fromEntries(open.map((l) => [l.id, editable(l.unit_cost)])),
  );
  const receive = useReceive(order.id);

  const lines = open
    .map((l) => ({ line: l, qty: (qty[l.id] ?? '').trim(), cost: (cost[l.id] ?? '').trim() }))
    .filter((x) => x.qty !== '' && x.qty !== '0');
  const valid = lines.length > 0 && lines.every((x) => QTY_RE.test(x.qty) && MONEY_RE.test(x.cost));

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    receive.mutate(
      {
        invoice_number: invoice.trim() || null,
        lines: lines.map((x) => ({
          line_id: x.line.id,
          qty: x.qty,
          // Ціну шлемо, лише якщо вона в накладній інша.
          unit_cost: x.cost !== editable(x.line.unit_cost) ? x.cost : null,
        })),
      },
      { onSuccess: () => setInvoice('') },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Прихід за накладною</CardTitle>
      </CardHeader>
      <CardBody>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3" noValidate>
          <label className="flex max-w-xs flex-col gap-1.5">
            <span className="text-sm font-medium text-ink">Номер накладної</span>
            <input value={invoice} maxLength={40} onChange={(e) => setInvoice(e.target.value)} className={inputClass} />
          </label>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {['Деталь', 'Лишилось', 'Приїхало', 'Ціна в накладній, ₴'].map((h) => (
                  <th key={h} className={thClass}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {open.map((l) => (
                <tr key={l.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-2 text-ink">{l.name}</td>
                  <td className="px-4 py-2 tabular text-ink-muted">
                    {remaining(l)} {UNIT_LABEL[l.unit] ?? l.unit}
                  </td>
                  <td className="px-4 py-2">
                    <input
                      value={qty[l.id] ?? ''}
                      onChange={(e) => setQty((q) => ({ ...q, [l.id]: e.target.value }))}
                      inputMode="decimal"
                      aria-label={`Приїхало: ${l.name}`}
                      className={`${cellInput} w-24`}
                    />
                  </td>
                  <td className="px-4 py-2">
                    <input
                      value={cost[l.id] ?? ''}
                      onChange={(e) => setCost((c) => ({ ...c, [l.id]: e.target.value }))}
                      inputMode="decimal"
                      aria-label={`Ціна в накладній: ${l.name}`}
                      className={`${cellInput} w-28`}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-ink-faint">
            Не приїхало — поставте 0. Решту можна прийняти наступною накладною.
          </p>
          <ErrorNote message={receive.error?.message} />
          <div>
            <Button type="submit" disabled={!valid || receive.isPending}>
              {receive.isPending ? 'Оприбуткування…' : 'Оприбуткувати'}
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

function Row({ label, value, className }: { label: string; value: string | null | undefined; className?: string }) {
  return (
    <div className={className}>
      <dt className="font-mono text-[11px] tracking-wider text-ink-faint uppercase">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{value || '—'}</dd>
    </div>
  );
}
