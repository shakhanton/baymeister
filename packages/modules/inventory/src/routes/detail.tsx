import { Badge, Button, Card, CardBody, CardHeader, CardTitle } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import { useCount, useStockItem, useUpdateItem, type Movement, type StockDetail } from '../api';
import { ErrorNote, formatMoney, formatQty, inputClass, thClass, UNIT_LABEL } from '../components/ui';

const KIND_LABEL: Record<Movement['kind'], string> = {
  receipt: 'прихід',
  issue: 'в наряд',
  count_plus: 'надлишок',
  count_minus: 'нестача',
};

export default function StockItemPage() {
  const { partId = '' } = useParams();
  const query = useStockItem(partId);

  if (query.isPending) {
    return <div className="h-40 max-w-5xl animate-pulse rounded-bm bg-surface-2" role="status" />;
  }
  if (query.isError) {
    return (
      <div className="flex max-w-5xl flex-col gap-3">
        <ErrorNote message={query.error.message} />
        <Link to="/inventory" className="text-sm text-accent underline underline-offset-2">
          ← До складу
        </Link>
      </div>
    );
  }

  const item = query.data;
  const unit = UNIT_LABEL[item.unit] ?? item.unit;

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <Link to="/inventory" className="text-sm text-accent underline underline-offset-2">
        ← До складу
      </Link>

      <Card>
        <CardHeader className="flex flex-wrap items-center gap-3">
          <CardTitle>{item.name}</CardTitle>
          <span className="font-mono text-sm text-ink-muted">
            {item.brand} {item.sku}
          </span>
          {item.low ? <Badge tone="danger">нижче мінімуму</Badge> : null}
        </CardHeader>
        <CardBody className="grid gap-4 sm:grid-cols-4">
          <Stat label="На складі" value={`${formatQty(item.on_hand)} ${unit}`} />
          <Stat label="Резерв" value={`${formatQty(item.reserved)} ${unit}`} />
          <Stat
            label="Вільно"
            value={`${formatQty(item.free)} ${unit}`}
            danger={item.free.startsWith('-') || item.low}
          />
          <Stat label="Собівартість" value={formatMoney(item.value)} />
        </CardBody>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <SettingsCard item={item} />
        <CountCard item={item} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Партії — у порядку списання</CardTitle>
        </CardHeader>
        <CardBody>
          {item.lots.length === 0 ? (
            <p className="text-sm text-ink-muted">Партій з залишком немає.</p>
          ) : (
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  {['Надійшла', 'Було', 'Лишилось', 'Ціна', 'Примітка'].map((h) => (
                    <th key={h} className={thClass}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {item.lots.map((lot) => (
                  <tr key={lot.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-2 tabular text-ink-muted">
                      {new Date(lot.received_at).toLocaleDateString('uk-UA')}
                    </td>
                    <td className="px-4 py-2 tabular text-ink-muted">{formatQty(lot.qty_received)}</td>
                    <td className="px-4 py-2 tabular font-medium text-ink">{formatQty(lot.qty_left)}</td>
                    <td className="px-4 py-2 tabular text-ink">{formatMoney(lot.unit_cost)}</td>
                    <td className="px-4 py-2 text-ink-muted">{lot.note ?? (lot.source === 'count' ? 'інвентаризація' : '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      {item.reservations.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Резерви під наряди</CardTitle>
          </CardHeader>
          <CardBody className="flex flex-col gap-1 text-sm">
            {item.reservations.map((r) => (
              <div key={r.line_id} className="flex gap-4">
                <span className="font-mono text-ink">{r.order_number ?? '—'}</span>
                <span className="tabular text-ink-muted">
                  {formatQty(r.qty)} {unit}
                </span>
              </div>
            ))}
            <p className="mt-2 text-xs text-ink-faint">
              Резерв знімається автоматично: списується, коли наряд закрито, і звільняється, коли скасовано.
            </p>
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Рух</CardTitle>
        </CardHeader>
        <CardBody>
          {item.movements.length === 0 ? (
            <p className="text-sm text-ink-muted">Руху ще не було.</p>
          ) : (
            <table className="w-full border-collapse text-sm">
              <tbody>
                {item.movements.map((m) => (
                  <tr key={m.id} className="border-b border-line last:border-0">
                    <td className="py-2 pr-4 tabular text-ink-muted">
                      {new Date(m.created_at).toLocaleString('uk-UA', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    <td className="py-2 pr-4 text-ink">{KIND_LABEL[m.kind]}</td>
                    <td className={`py-2 pr-4 tabular font-medium ${m.qty.startsWith('-') ? 'text-danger' : 'text-ready'}`}>
                      {m.qty.startsWith('-') ? '' : '+'}
                      {formatQty(m.qty)}
                    </td>
                    <td className="py-2 pr-4 tabular text-ink-muted">{formatMoney(m.cost)}</td>
                    <td className="py-2 text-ink-muted">
                      {m.order_number ? <span className="font-mono">{m.order_number} </span> : null}
                      {m.note}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function Stat({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div>
      <div className="font-mono text-[11px] tracking-wider text-ink-faint uppercase">{label}</div>
      <div className={`mt-1 font-cond text-2xl leading-none font-bold tabular ${danger ? 'text-danger' : 'text-ink'}`}>
        {value}
      </div>
    </div>
  );
}

function SettingsCard({ item }: { item: StockDetail }) {
  const update = useUpdateItem(item.part_id);
  const [location, setLocation] = useState(item.location ?? '');
  const [minQty, setMinQty] = useState(item.min_qty.replace(/\.?0+$/, '') || '0');

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    update.mutate({ location: location.trim() || null, min_qty: minQty.trim() || '0' });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Зберігання</CardTitle>
      </CardHeader>
      <CardBody>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Комірка</span>
              <input value={location} maxLength={20} onChange={(e) => setLocation(e.target.value)} placeholder="A-03-2" className={`${inputClass} font-mono`} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Мінімум</span>
              <input value={minQty} onChange={(e) => setMinQty(e.target.value)} inputMode="decimal" className={`${inputClass} tabular`} />
            </label>
          </div>
          <p className="text-xs text-ink-faint">Коли вільного стає менше за мінімум, закупівлі отримують сигнал.</p>
          <ErrorNote message={update.error?.message} />
          <div>
            <Button type="submit" variant="outline" size="sm" disabled={update.isPending}>
              Зберегти
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

function CountCard({ item }: { item: StockDetail }) {
  const count = useCount(item.part_id);
  const [counted, setCounted] = useState('');
  const [note, setNote] = useState('');

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    count.mutate(
      { counted: counted.trim(), note: note.trim() || null },
      {
        onSuccess: () => {
          setCounted('');
          setNote('');
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Інвентаризація</CardTitle>
      </CardHeader>
      <CardBody>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Фактично нараховано</span>
              <input value={counted} onChange={(e) => setCounted(e.target.value)} inputMode="decimal" className={`${inputClass} tabular`} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Примітка</span>
              <input value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} className={inputClass} />
            </label>
          </div>
          <p className="text-xs text-ink-faint">
            Нестача списується з найстаріших партій, надлишок стає партією за ціною останнього приходу.
          </p>
          <ErrorNote message={count.error?.message} />
          <div>
            <Button type="submit" variant="outline" size="sm" disabled={!counted.trim() || count.isPending}>
              Провести
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
