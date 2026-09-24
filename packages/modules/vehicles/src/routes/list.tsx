import { Button, Card, CardBody, CardHeader, CardTitle, EmptyState } from '@baymeister/ui';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useCreateVehicle, useVehicles, type VehicleCreate } from '../api';
import { VehicleForm, type VehicleFormValues } from '../components/vehicle-form';
import { formatKm } from '../format';

const PAGE_SIZE = 25;

export default function VehiclesList() {
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);

  const search = params.get('search') ?? '';
  const archived = params.get('archived') === '1';
  const offset = Number(params.get('offset') ?? 0);

  const query = useVehicles({ search: search || undefined, archived, limit: PAGE_SIZE, offset });
  const create = useCreateVehicle();

  function patchParams(next: Record<string, string | null>) {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === '') merged.delete(key);
      else merged.set(key, value);
    }
    if (!('offset' in next)) merged.delete('offset');
    setParams(merged, { replace: true });
  }

  function handleCreate(values: VehicleFormValues) {
    const body: VehicleCreate = {
      customer_id: values.customer_id,
      plate: values.plate,
      vin: values.vin || null,
      make: values.make,
      model: values.model,
      year: values.year ?? null,
      color: values.color || null,
      notes: values.notes || null,
      mileage_km: values.mileage_km ?? null,
    };
    // Помилку показує форма через create.error — тут її не ловимо.
    create.mutate(body, { onSuccess: () => setCreating(false) });
  }

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => patchParams({ search: e.target.value })}
          placeholder="Номер, VIN, марка або власник"
          aria-label="Пошук автомобілів"
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

        <Button className="ml-auto" onClick={() => setCreating((v) => !v)}>
          {creating ? 'Згорнути' : 'Додати автомобіль'}
        </Button>
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Новий автомобіль</CardTitle>
          </CardHeader>
          <CardBody>
            <VehicleForm
              mode="create"
              submitLabel="Додати"
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
          title={search ? 'Нічого не знайдено' : archived ? 'Архів порожній' : 'Автомобілів ще немає'}
          description={
            search
              ? 'Спробуйте інший запит або очистіть фільтри.'
              : 'Перший автомобіль зʼявиться тут одразу після додавання.'
          }
        />
      ) : null}

      {query.data && query.data.items.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-bm border border-line bg-surface">
            <table className="w-full min-w-[720px] border-collapse text-sm">
              <thead>
                <tr className="bg-surface-2">
                  {['Держномер', 'Автомобіль', 'Власник', 'Пробіг'].map((h) => (
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
                {query.data.items.map((vehicle) => (
                  <tr key={vehicle.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        to={`/vehicles/${vehicle.id}`}
                        className="font-mono font-medium text-accent hover:underline"
                      >
                        {vehicle.plate}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-ink">
                      {vehicle.make} {vehicle.model}
                      {vehicle.year ? <span className="text-ink-muted"> · {vehicle.year}</span> : null}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-ink">{vehicle.customer_name}</div>
                      <div className="font-mono text-xs text-ink-muted">{vehicle.customer_phone}</div>
                    </td>
                    <td className="px-4 py-3 tabular text-ink-muted">
                      {vehicle.mileage_km != null ? formatKm(vehicle.mileage_km) : '—'}
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
