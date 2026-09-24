import { Button, Card, CardBody, EmptyState } from '@baymeister/ui';
import { Fragment, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useArchivePart, useParts, useSavePart, type Part } from '../api';
import { PartForm, type PartFormValues } from '../components/part-form';
import {
  CatalogTabs,
  ErrorNote,
  formatMoney,
  ListSkeleton,
  thClass,
  UNIT_LABEL,
} from '../components/ui';

export default function PartsPage() {
  const [params, setParams] = useSearchParams();
  const [editing, setEditing] = useState<string | 'new' | null>(null);

  const search = params.get('search') ?? '';
  const archived = params.get('archived') === '1';
  const query = useParts({ search: search || undefined, archived, limit: 100 });
  const archive = useArchivePart();

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

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => patchParams({ search: e.target.value })}
          placeholder="Артикул, назва або бренд"
          aria-label="Пошук запчастин"
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
          {editing === 'new' ? 'Згорнути' : 'Додати запчастину'}
        </Button>
      </div>

      {editing === 'new' ? (
        <Card>
          <CardBody>
            <PartEditor onDone={() => setEditing(null)} />
          </CardBody>
        </Card>
      ) : null}

      {query.isPending ? <ListSkeleton /> : null}
      <ErrorNote message={query.error?.message} />
      <ErrorNote message={archive.error?.message} />

      {query.data && query.data.items.length === 0 ? (
        <EmptyState
          title={search ? 'Нічого не знайдено' : archived ? 'Архів порожній' : 'Каталог порожній'}
          description={
            search ? 'Спробуйте інший запит.' : 'Залишки на складі веде блок «Склад» — тут лише ціни.'
          }
        />
      ) : null}

      {query.data && query.data.items.length > 0 ? (
        <div className="overflow-x-auto rounded-bm border border-line bg-surface">
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr className="bg-surface-2">
                {['Артикул', 'Запчастина', 'Од.', 'Ціна', ''].map((h) => (
                  <th key={h} className={thClass}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((part) => (
                <Fragment key={part.id}>
                  <tr className="border-b border-line last:border-0">
                    <td className="px-4 py-3 font-mono text-ink-muted">{part.sku}</td>
                    <td className="px-4 py-3">
                      <div className="text-ink">{part.name}</div>
                      <div className="text-xs text-ink-faint">{part.brand}</div>
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{UNIT_LABEL[part.unit]}</td>
                    <td className="px-4 py-3 tabular font-medium text-ink">
                      {formatMoney(part.price)}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {!part.archived_at ? (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditing(editing === part.id ? null : part.id)}
                          >
                            {editing === part.id ? 'Згорнути' : 'Змінити'}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={archive.isPending}
                            onClick={() => archive.mutate(part.id)}
                          >
                            В архів
                          </Button>
                        </>
                      ) : null}
                    </td>
                  </tr>
                  {editing === part.id ? (
                    <tr className="border-b border-line bg-surface-2">
                      <td colSpan={5} className="px-4 py-4">
                        <PartEditor part={part} onDone={() => setEditing(null)} />
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

function PartEditor({ part, onDone }: { part?: Part; onDone: () => void }) {
  const save = useSavePart(part?.id);

  function handleSubmit(values: PartFormValues) {
    // Помилку показує форма через save.error — тут її не ловимо.
    save.mutate(values, { onSuccess: onDone });
  }

  return (
    <PartForm
      part={part}
      pending={save.isPending}
      error={save.error?.message ?? null}
      onSubmit={handleSubmit}
      onCancel={onDone}
    />
  );
}
