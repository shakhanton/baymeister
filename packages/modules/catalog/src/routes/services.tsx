import { Badge, Button, Card, CardBody, EmptyState } from '@baymeister/ui';
import { Fragment, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router';
import {
  useArchiveService,
  useLaborRate,
  useSaveService,
  useServices,
  useSetLaborRate,
  type Service,
} from '../api';
import { ServiceForm, type ServiceFormValues } from '../components/service-form';
import {
  CatalogTabs,
  ErrorNote,
  formatMoney,
  inputClass,
  ListSkeleton,
  MONEY_RE,
  thClass,
} from '../components/ui';

export default function ServicesPage() {
  const [params, setParams] = useSearchParams();
  const [editing, setEditing] = useState<string | 'new' | null>(null);

  const search = params.get('search') ?? '';
  const archived = params.get('archived') === '1';
  const query = useServices({ search: search || undefined, archived, limit: 100 });
  const archive = useArchiveService();

  function patchParams(next: Record<string, string | null>) {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === '') merged.delete(key);
      else merged.set(key, value);
    }
    setParams(merged, { replace: true });
  }

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <CatalogTabs />
      <LaborRateCard />

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => patchParams({ search: e.target.value })}
          placeholder="Код, назва або категорія"
          aria-label="Пошук робіт"
          className="h-9 w-72 rounded-bm border border-line-strong bg-surface px-3 text-sm placeholder:text-ink-faint"
        />
        <label className="flex items-center gap-2 text-sm text-ink-muted">
          <input
            type="checkbox"
            checked={archived}
            onChange={(e) => patchParams({ archived: e.target.checked ? '1' : null })}
          />
          Архів
        </label>
        <Button className="ml-auto" onClick={() => setEditing(editing === 'new' ? null : 'new')}>
          {editing === 'new' ? 'Згорнути' : 'Додати роботу'}
        </Button>
      </div>

      {editing === 'new' ? (
        <Card>
          <CardBody>
            <ServiceEditor onDone={() => setEditing(null)} />
          </CardBody>
        </Card>
      ) : null}

      {query.isPending ? <ListSkeleton /> : null}
      <ErrorNote message={query.error?.message} />
      <ErrorNote message={archive.error?.message} />

      {query.data && query.data.items.length === 0 ? (
        <EmptyState
          title={search ? 'Нічого не знайдено' : archived ? 'Архів порожній' : 'Робіт ще немає'}
          description={search ? 'Спробуйте інший запит.' : 'Додайте першу роботу до прайсу.'}
        />
      ) : null}

      {query.data && query.data.items.length > 0 ? (
        <div className="overflow-x-auto rounded-bm border border-line bg-surface">
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr className="bg-surface-2">
                {['Код', 'Робота', 'Н/год', 'Ціна', ''].map((h) => (
                  <th key={h} className={thClass}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((service) => (
                <Fragment key={service.id}>
                  <tr className="border-b border-line last:border-0">
                    <td className="px-4 py-3 font-mono text-ink-muted">{service.code}</td>
                    <td className="px-4 py-3">
                      <div className="text-ink">{service.name}</div>
                      <div className="text-xs text-ink-faint">{service.category}</div>
                    </td>
                    <td className="px-4 py-3 tabular text-ink-muted">{service.norm_hours}</td>
                    <td className="px-4 py-3 tabular">
                      <span className="font-medium text-ink">{formatMoney(service.price)}</span>
                      {service.price_source === 'fixed' ? (
                        <Badge tone="neutral" className="ml-2">
                          фікс.
                        </Badge>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {!service.archived_at ? (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditing(editing === service.id ? null : service.id)}
                          >
                            {editing === service.id ? 'Згорнути' : 'Змінити'}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={archive.isPending}
                            onClick={() => archive.mutate(service.id)}
                          >
                            В архів
                          </Button>
                        </>
                      ) : null}
                    </td>
                  </tr>
                  {editing === service.id ? (
                    <tr className="border-b border-line bg-surface-2">
                      <td colSpan={5} className="px-4 py-4">
                        <ServiceEditor service={service} onDone={() => setEditing(null)} />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function ServiceEditor({ service, onDone }: { service?: Service; onDone: () => void }) {
  const save = useSaveService(service?.id);

  function handleSubmit(values: ServiceFormValues) {
    // Помилку показує форма через save.error — тут її не ловимо.
    save.mutate(
      {
        code: values.code,
        name: values.name,
        category: values.category,
        norm_hours: values.norm_hours,
        fixed_price: values.fixed_price || null,
      },
      { onSuccess: onDone },
    );
  }

  return (
    <ServiceForm
      service={service}
      pending={save.isPending}
      error={save.error?.message ?? null}
      onSubmit={handleSubmit}
      onCancel={onDone}
    />
  );
}

/**
 * Ставка — одна на весь прайс. Нова ставка не переписує стару, а додається з
 * поточного моменту: відкриті раніше наряди рахуються за своєю.
 */
function LaborRateCard() {
  const rate = useLaborRate();
  const setRate = useSetLaborRate();
  const [amount, setAmount] = useState('');

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setRate.mutate(amount.trim(), { onSuccess: () => setAmount('') });
  }

  const valid = MONEY_RE.test(amount.trim());

  return (
    <Card>
      <CardBody className="flex flex-wrap items-end gap-6">
        <div>
          <div className="font-mono text-[11px] tracking-wider text-ink-faint uppercase">
            Вартість нормо-години
          </div>
          <div className="mt-1 font-cond text-3xl leading-none font-bold tabular text-ink">
            {rate.isPending ? '…' : rate.data ? formatMoney(rate.data.amount) : 'не задана'}
          </div>
          {rate.data ? (
            <div className="mt-1 text-xs text-ink-faint">
              діє з {new Date(rate.data.effective_from).toLocaleString('uk-UA')}
            </div>
          ) : (
            <div className="mt-1 text-xs text-ink-faint">без неї ціни робіт невідомі</div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="ml-auto flex items-end gap-2">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-ink">Нова ставка, ₴</span>
            <input
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              inputMode="decimal"
              placeholder="850"
              className={`${inputClass} w-32 tabular`}
            />
          </label>
          <Button type="submit" variant="outline" disabled={!valid || setRate.isPending}>
            Застосувати
          </Button>
        </form>
        {setRate.error ? (
          <div className="w-full">
            <ErrorNote message={setRate.error.message} />
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
