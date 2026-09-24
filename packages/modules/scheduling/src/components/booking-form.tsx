import { Button } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { useBook, useCustomerSearch, useCustomerVehicles, type Bay } from '../api';
import { addMinutes, hhmm } from '../time';

const DURATIONS = [30, 60, 90, 120, 180, 240];

const inputClass =
  'h-9 w-full rounded-bm border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-faint';

/**
 * Запис на вільний слот. Пост і час беруться з клітинки, на яку клікнули;
 * клієнт — пошуком, авто — зі списку автомобілів цього клієнта.
 */
export function BookingForm({
  bay,
  startsAt,
  onDone,
}: {
  bay: Bay;
  startsAt: Date;
  onDone: () => void;
}) {
  const book = useBook();
  const [duration, setDuration] = useState(60);
  const [customer, setCustomer] = useState<{ id: string; name: string; phone: string } | null>(null);
  const [vehicleId, setVehicleId] = useState('');
  const [note, setNote] = useState('');
  const [search, setSearch] = useState('');

  const results = useCustomerSearch(search);
  const vehicles = useCustomerVehicles(customer?.id ?? null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!customer) return;
    // Помилку (зокрема «пост зайнятий») показує форма через book.error.
    book.mutate(
      {
        bay_id: bay.id,
        customer_id: customer.id,
        vehicle_id: vehicleId || null,
        starts_at: startsAt.toISOString(),
        ends_at: addMinutes(startsAt, duration).toISOString(),
        source: 'phone',
        note: note || null,
      },
      { onSuccess: onDone },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      <div className="text-sm text-ink-muted">
        <span className="font-medium text-ink">{bay.name}</span> · {hhmm(startsAt)}–
        {hhmm(addMinutes(startsAt, duration))}
      </div>

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">Тривалість</span>
        <select
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value))}
          className={inputClass}
        >
          {DURATIONS.map((m) => (
            <option key={m} value={m}>
              {m < 60 ? `${m} хв` : `${m / 60} год`.replace('.5', ',5')}
            </option>
          ))}
        </select>
      </label>

      {customer ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink">Клієнт</span>
          <div className="flex items-center gap-2 rounded-bm border border-line-strong px-3 py-2 text-sm">
            <span className="text-ink">{customer.name}</span>
            <span className="font-mono text-xs text-ink-muted">{customer.phone}</span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="ml-auto"
              onClick={() => {
                setCustomer(null);
                setVehicleId('');
              }}
            >
              Змінити
            </Button>
          </div>
        </div>
      ) : (
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink">Клієнт</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Імʼя або телефон"
            className={inputClass}
          />
          {search.trim().length >= 2 ? (
            <ul className="overflow-hidden rounded-bm border border-line bg-surface" role="listbox">
              {results.data?.length === 0 ? (
                <li className="px-3 py-2 text-sm text-ink-muted">Нікого не знайдено</li>
              ) : null}
              {results.data?.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected="false"
                    className="flex w-full gap-2 px-3 py-2 text-left text-sm hover:bg-surface-2"
                    onClick={() => setCustomer({ id: c.id, name: c.name, phone: c.phone })}
                  >
                    <span className="text-ink">{c.name}</span>
                    <span className="font-mono text-xs text-ink-muted">{c.phone}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </label>
      )}

      {customer ? (
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink">Автомобіль</span>
          <select
            value={vehicleId}
            onChange={(e) => setVehicleId(e.target.value)}
            className={inputClass}
          >
            <option value="">— не вказано —</option>
            {vehicles.data?.map((v) => (
              <option key={v.id} value={v.id}>
                {v.plate} · {v.make} {v.model}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">Примітка</span>
        <input
          value={note}
          maxLength={500}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Напр. стукіт у підвісці"
          className={inputClass}
        />
      </label>

      {book.error ? (
        <p role="alert" className="rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
          {book.error.message}
        </p>
      ) : null}

      <div className="flex gap-2">
        <Button type="submit" disabled={!customer || book.isPending}>
          {book.isPending ? 'Запис…' : 'Записати'}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Скасувати
        </Button>
      </div>
    </form>
  );
}
