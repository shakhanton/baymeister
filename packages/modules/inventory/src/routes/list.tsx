import { Badge, Button, Card, CardBody, CardHeader, CardTitle, EmptyState } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router';
import { usePartSearch, useReceive, useStock } from '../api';
import { ErrorNote, formatMoney, formatQty, inputClass, thClass, UNIT_LABEL } from '../components/ui';

const MONEY_RE = /^\d{1,9}([.,]\d{1,2})?$/;
const QTY_RE = /^\d{1,6}([.,]\d{1,3})?$/;

export default function StockList() {
  const [params, setParams] = useSearchParams();
  const [receiving, setReceiving] = useState(false);
  const search = params.get('search') ?? '';
  const low = params.get('low') === '1';
  const query = useStock(search, low);

  function patchParams(next: Record<string, string | null>) {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === '') merged.delete(key);
      else merged.set(key, value);
    }
    setParams(merged, { replace: true });
  }

  const totalValue = query.data?.items.reduce((sum, i) => sum + Math.round(Number(i.value) * 100), 0);

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => patchParams({ search: e.target.value })}
          placeholder="Артикул, бренд, назва або комірка"
          aria-label="Пошук на складі"
          className="h-9 w-80 rounded-bm border border-line-strong bg-surface px-3 text-sm placeholder:text-ink-faint"
        />
        <label className="flex items-center gap-2 text-sm text-ink-muted">
          <input
            type="checkbox"
            checked={low}
            onChange={(e) => patchParams({ low: e.target.checked ? '1' : null })}
          />
          Тільки нижче мінімуму
        </label>
        <Button className="ml-auto" onClick={() => setReceiving((v) => !v)}>
          {receiving ? 'Згорнути' : 'Прихід'}
        </Button>
      </div>

      {receiving ? (
        <Card>
          <CardHeader>
            <CardTitle>Прихід партії</CardTitle>
          </CardHeader>
          <CardBody>
            <ReceiptForm onDone={() => setReceiving(false)} />
          </CardBody>
        </Card>
      ) : null}

      <ErrorNote message={query.error?.message} />

      {query.data && query.data.items.length === 0 ? (
        <EmptyState
          title={search || low ? 'Нічого не знайдено' : 'Склад порожній'}
          description={
            search || low
              ? 'Спробуйте інший запит або зніміть фільтр.'
              : 'Оприбуткуйте першу партію — деталь береться з прайсу.'
          }
        />
      ) : null}

      {query.data && query.data.items.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-bm border border-line bg-surface">
            <table className="w-full min-w-[860px] border-collapse text-sm">
              <thead>
                <tr className="bg-surface-2">
                  {['Деталь', 'Комірка', 'На складі', 'Резерв', 'Вільно', 'Собівартість'].map((h) => (
                    <th key={h} className={thClass}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((item) => (
                  <tr key={item.part_id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <Link to={`/inventory/${item.part_id}`} className="font-medium text-accent hover:underline">
                        {item.name}
                      </Link>
                      <div className="font-mono text-xs text-ink-faint">
                        {item.brand} {item.sku}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-ink-muted">{item.location ?? '—'}</td>
                    <td className="px-4 py-3 tabular text-ink">
                      {formatQty(item.on_hand)} {UNIT_LABEL[item.unit] ?? item.unit}
                    </td>
                    <td className="px-4 py-3 tabular text-ink-muted">{formatQty(item.reserved)}</td>
                    <td className="px-4 py-3 tabular">
                      <span className={item.free.startsWith('-') ? 'font-medium text-danger' : 'text-ink'}>
                        {formatQty(item.free)}
                      </span>
                      {item.low ? (
                        <Badge tone="danger" className="ml-2">
                          мало
                        </Badge>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 tabular text-ink-muted">{formatMoney(item.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-ink-faint">
            Позицій: {query.data.total}
            {totalValue !== undefined ? ` · собівартість на сторінці: ${formatMoney((totalValue / 100).toFixed(2))}` : ''}
          </p>
        </>
      ) : null}
    </div>
  );
}

function ReceiptForm({ onDone }: { onDone: () => void }) {
  const [search, setSearch] = useState('');
  const [part, setPart] = useState<{ id: string; label: string } | null>(null);
  const [qty, setQty] = useState('');
  const [cost, setCost] = useState('');
  const [note, setNote] = useState('');
  const results = usePartSearch(search);
  const receive = useReceive();

  const valid = part !== null && QTY_RE.test(qty.trim()) && MONEY_RE.test(cost.trim());

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!part) return;
    receive.mutate(
      { part_id: part.id, qty: qty.trim(), unit_cost: cost.trim(), note: note.trim() || null },
      { onSuccess: onDone },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-4" noValidate>
      {part ? (
        <div className="flex flex-col gap-1.5 sm:col-span-4">
          <span className="text-sm font-medium text-ink">Деталь</span>
          <div className="flex items-center gap-2 rounded-bm border border-line-strong px-3 py-2 text-sm">
            <span className="text-ink">{part.label}</span>
            <Button type="button" variant="ghost" size="sm" className="ml-auto" onClick={() => setPart(null)}>
              Змінити
            </Button>
          </div>
        </div>
      ) : (
        <label className="flex flex-col gap-1.5 sm:col-span-4">
          <span className="text-sm font-medium text-ink">Деталь з прайсу</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Артикул, назва або бренд"
            className={inputClass}
          />
          {search.trim() ? (
            <ul className="overflow-hidden rounded-bm border border-line bg-surface" role="listbox">
              {results.data?.length === 0 ? (
                <li className="px-3 py-2 text-sm text-ink-muted">У прайсі такої немає — спершу додайте її туди</li>
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
      <label className="flex flex-col gap-1.5 sm:col-span-2">
        <span className="text-sm font-medium text-ink">Примітка</span>
        <input
          value={note}
          maxLength={200}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Напр. накладна № 1234"
          className={inputClass}
        />
      </label>

      <div className="sm:col-span-4">
        <ErrorNote message={receive.error?.message} />
      </div>
      <div className="flex gap-2 sm:col-span-4">
        <Button type="submit" disabled={!valid || receive.isPending}>
          {receive.isPending ? 'Оприбуткування…' : 'Оприбуткувати'}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Скасувати
        </Button>
      </div>
    </form>
  );
}
