import { Button } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { useCustomer, useCustomerSearch, useCustomerVehicles, useOpenOrder } from '../api';
import { ErrorNote, inputClass } from './ui';

/**
 * Відкрити наряд. Можна прийти з планувальника — тоді клієнт, авто й запис
 * уже відомі (параметри в URL), лишається дописати скаргу й пробіг.
 */
export function OpenOrderForm({
  initial,
  onCancel,
}: {
  initial: { customerId: string | null; vehicleId: string | null; appointmentId: string | null };
  onCancel: () => void;
}) {
  const navigate = useNavigate();
  const open = useOpenOrder();
  const [customerId, setCustomerId] = useState<string | null>(initial.customerId);
  const [vehicleId, setVehicleId] = useState(initial.vehicleId ?? '');
  const [search, setSearch] = useState('');
  const [complaint, setComplaint] = useState('');
  const [mileage, setMileage] = useState('');

  const customer = useCustomer(customerId);
  const results = useCustomerSearch(search);
  const vehicles = useCustomerVehicles(customerId);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!customerId || !vehicleId) return;
    open.mutate(
      {
        customer_id: customerId,
        vehicle_id: vehicleId,
        appointment_id: initial.appointmentId,
        complaint: complaint.trim() || null,
        mileage_km: mileage ? Number(mileage) : null,
      },
      // Одразу в наряд — додавати роботи.
      { onSuccess: (order) => navigate(`/work-orders/${order.id}`) },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2" noValidate>
      {customerId ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink">Клієнт</span>
          <div className="flex items-center gap-2 rounded-bm border border-line-strong px-3 py-2 text-sm">
            <span className="text-ink">{customer.data?.name ?? '…'}</span>
            <span className="font-mono text-xs text-ink-muted">{customer.data?.phone}</span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="ml-auto"
              onClick={() => {
                setCustomerId(null);
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
                    onClick={() => setCustomerId(c.id)}
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

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">Автомобіль</span>
        <select
          value={vehicleId}
          disabled={!customerId}
          onChange={(e) => setVehicleId(e.target.value)}
          className={inputClass}
        >
          <option value="">{customerId ? '— оберіть —' : 'спершу клієнт'}</option>
          {vehicles.data?.map((v) => (
            <option key={v.id} value={v.id}>
              {v.plate} · {v.make} {v.model}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">Пробіг, км</span>
        <input
          type="number"
          min={0}
          value={mileage}
          onChange={(e) => setMileage(e.target.value)}
          className={`${inputClass} tabular`}
        />
      </label>

      <label className="flex flex-col gap-1.5 sm:col-span-2">
        <span className="text-sm font-medium text-ink">Скарга клієнта</span>
        <textarea
          value={complaint}
          maxLength={2000}
          rows={2}
          onChange={(e) => setComplaint(e.target.value)}
          placeholder="Зі слів клієнта: «стукає спереду справа на ямах»"
          className={`${inputClass} h-auto resize-y py-2`}
        />
      </label>

      <div className="sm:col-span-2">
        <ErrorNote message={open.error?.message} />
      </div>

      <div className="flex gap-2 sm:col-span-2">
        <Button type="submit" disabled={!customerId || !vehicleId || open.isPending}>
          {open.isPending ? 'Відкриття…' : 'Відкрити наряд'}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Скасувати
        </Button>
      </div>
    </form>
  );
}
