import { Badge, Button, Card, CardBody, CardHeader, CardTitle } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import {
  useArchiveVehicle,
  useMileage,
  useRecordMileage,
  useUpdateVehicle,
  useVehicle,
  type VehicleUpdate,
} from '../api';
import { VehicleForm, type VehicleFormValues } from '../components/vehicle-form';
import { formatKm } from '../format';

export default function VehicleDetail() {
  const { vehicleId = '' } = useParams();
  const [editing, setEditing] = useState(false);

  const query = useVehicle(vehicleId);
  const update = useUpdateVehicle(vehicleId);
  const archive = useArchiveVehicle(vehicleId);

  if (query.isPending) {
    return <div className="h-40 max-w-3xl animate-pulse rounded-bm bg-surface-2" role="status" />;
  }

  if (query.isError) {
    return (
      <div className="flex max-w-3xl flex-col gap-3">
        <p role="alert" className="rounded-bm bg-danger-soft px-4 py-3 text-sm text-danger">
          {query.error.message}
        </p>
        <Link to="/vehicles" className="text-sm text-accent underline underline-offset-2">
          ← До списку автомобілів
        </Link>
      </div>
    );
  }

  const vehicle = query.data;

  function handleSave(values: VehicleFormValues) {
    const body: VehicleUpdate = {
      plate: values.plate,
      vin: values.vin || null,
      make: values.make,
      model: values.model,
      year: values.year ?? null,
      color: values.color || null,
      notes: values.notes || null,
    };
    // Той самий власник — не надсилаємо: бекенд не піде в customers зайвий раз.
    if (values.customer_id !== vehicle.customer_id) body.customer_id = values.customer_id;
    // Помилку показує форма через update.error — тут її не ловимо.
    update.mutate(body, { onSuccess: () => setEditing(false) });
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <Link to="/vehicles" className="text-sm text-accent underline underline-offset-2">
        ← До списку автомобілів
      </Link>

      <Card>
        <CardHeader className="flex flex-wrap items-center gap-3">
          <CardTitle>
            {vehicle.make} {vehicle.model}
          </CardTitle>
          <Badge tone="accent">{vehicle.plate}</Badge>
          {vehicle.archived_at ? <Badge tone="planned">в архіві</Badge> : null}

          {!vehicle.archived_at ? (
            <div className="ml-auto flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditing((v) => !v)}>
                {editing ? 'Скасувати' : 'Редагувати'}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={archive.isPending}
                onClick={() => archive.mutate()}
              >
                Архівувати
              </Button>
            </div>
          ) : null}
        </CardHeader>

        <CardBody>
          {editing ? (
            <VehicleForm
              mode="edit"
              defaultValues={vehicle}
              submitLabel="Зберегти"
              pending={update.isPending}
              error={update.error?.message ?? null}
              onSubmit={handleSave}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
              <Row label="Власник" value={`${vehicle.customer_name} · ${vehicle.customer_phone}`} />
              <Row label="VIN" value={vehicle.vin} mono />
              <Row label="Рік" value={vehicle.year ? String(vehicle.year) : null} />
              <Row label="Колір" value={vehicle.color} />
              <Row
                label="Пробіг"
                value={vehicle.mileage_km != null ? formatKm(vehicle.mileage_km) : null}
              />
              <Row label="Примітки" value={vehicle.notes} className="sm:col-span-2" />
            </dl>
          )}

          {archive.isError ? (
            <p role="alert" className="mt-4 rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
              {archive.error.message}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <MileageCard vehicleId={vehicle.id} archived={Boolean(vehicle.archived_at)} />

      <p className="text-xs text-ink-faint">
        Наряди по цьому автомобілю зʼявляться тут, коли блок{' '}
        <span className="font-mono">work-orders</span> стане готовим.
      </p>
    </div>
  );
}

function MileageCard({ vehicleId, archived }: { vehicleId: string; archived: boolean }) {
  const history = useMileage(vehicleId);
  const record = useRecordMileage(vehicleId);
  const [km, setKm] = useState('');
  const [note, setNote] = useState('');

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    record.mutate(
      { km: Number(km), note: note || null },
      {
        onSuccess: () => {
          setKm('');
          setNote('');
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Історія пробігу</CardTitle>
      </CardHeader>
      <CardBody className="flex flex-col gap-4">
        {!archived ? (
          <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Пробіг, км</span>
              <input
                type="number"
                min={0}
                required
                value={km}
                onChange={(e) => setKm(e.target.value)}
                className="h-9 w-36 rounded-bm border border-line-strong bg-surface px-3 text-sm tabular"
              />
            </label>
            <label className="flex flex-1 flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Примітка</span>
              <input
                value={note}
                maxLength={200}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Напр. ТО-2"
                className="h-9 rounded-bm border border-line-strong bg-surface px-3 text-sm"
              />
            </label>
            <Button type="submit" disabled={record.isPending || km === ''}>
              Записати
            </Button>
          </form>
        ) : null}

        {record.isError ? (
          <p role="alert" className="rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
            {record.error.message}
          </p>
        ) : null}

        {history.data && history.data.length > 0 ? (
          <ul className="flex flex-col divide-y divide-line text-sm">
            {history.data.map((r) => (
              <li key={r.id} className="flex items-center gap-4 py-2">
                <span className="w-28 tabular font-medium text-ink">{formatKm(r.km)}</span>
                <span className="w-36 tabular text-ink-muted">
                  {new Date(r.recorded_at).toLocaleDateString('uk-UA')}
                </span>
                <span className="text-ink-muted">{r.note ?? ''}</span>
              </li>
            ))}
          </ul>
        ) : history.data ? (
          <p className="text-sm text-ink-muted">Записів ще немає.</p>
        ) : null}
      </CardBody>
    </Card>
  );
}

function Row({
  label,
  value,
  mono,
  className,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="font-mono text-[11px] tracking-wider text-ink-faint uppercase">{label}</dt>
      <dd className={`mt-0.5 text-sm text-ink ${mono ? 'font-mono' : ''}`}>{value || '—'}</dd>
    </div>
  );
}
