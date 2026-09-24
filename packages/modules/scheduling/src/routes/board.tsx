import { Button, Card, CardBody, CardHeader, CardTitle, cn, EmptyState } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router';
import { useBays, useCreateBay, useDay, type Appointment, type Bay, type BayKind } from '../api';
import { AppointmentCard, STATUS_LABEL } from '../components/appointment-card';
import { BookingForm } from '../components/booking-form';
import {
  addDays,
  DAY_END_HOUR,
  DAY_START_HOUR,
  hhmm,
  isoDate,
  minutesFromOpen,
  parseIsoDate,
  PX_PER_MINUTE,
  SLOT_MINUTES,
  slotsOfDay,
  startOfDay,
} from '../time';

const HEIGHT = (DAY_END_HOUR - DAY_START_HOUR) * 60 * PX_PER_MINUTE;

const STATUS_STYLE: Record<Appointment['status'], string> = {
  booked: 'border-accent bg-accent-soft text-ink',
  arrived: 'border-wip bg-wip-soft text-ink',
  completed: 'border-ready bg-ready-soft text-ink-muted',
  cancelled: 'border-line bg-surface-2 text-ink-faint line-through',
  no_show: 'border-danger bg-danger-soft text-ink-muted',
};

type Panel =
  | { kind: 'book'; bay: Bay; startsAt: Date }
  | { kind: 'appointment'; id: string }
  | { kind: 'bay' }
  | null;

export default function Board() {
  const [params, setParams] = useSearchParams();
  const day = parseIsoDate(params.get('date'));
  const [panel, setPanel] = useState<Panel>(null);

  const bays = useBays();
  const appointments = useDay(day.toISOString(), addDays(day, 1).toISOString());

  function goTo(date: Date) {
    setParams({ date: isoDate(date) }, { replace: true });
    setPanel(null);
  }

  const selected =
    panel?.kind === 'appointment'
      ? appointments.data?.find((a) => a.id === panel.id) ?? null
      : null;
  const bayName = (id: string) => bays.data?.find((b) => b.id === id)?.name ?? '—';
  const isToday = isoDate(day) === isoDate(new Date());

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => goTo(addDays(day, -1))} aria-label="Попередній день">
          ←
        </Button>
        <Button variant={isToday ? 'primary' : 'outline'} size="sm" onClick={() => goTo(startOfDay(new Date()))}>
          Сьогодні
        </Button>
        <Button variant="outline" size="sm" onClick={() => goTo(addDays(day, 1))} aria-label="Наступний день">
          →
        </Button>
        <input
          type="date"
          value={isoDate(day)}
          onChange={(e) => e.target.value && goTo(parseIsoDate(e.target.value))}
          aria-label="Дата"
          className="h-8 rounded-bm border border-line-strong bg-surface px-2 text-sm"
        />
        <span className="ml-2 font-cond text-lg font-semibold text-ink capitalize">
          {day.toLocaleDateString('uk-UA', { weekday: 'long', day: 'numeric', month: 'long' })}
        </span>
        <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setPanel({ kind: 'bay' })}>
          Додати пост
        </Button>
      </div>

      {bays.error || appointments.error ? (
        <p role="alert" className="rounded-bm bg-danger-soft px-4 py-3 text-sm text-danger">
          {(bays.error ?? appointments.error)?.message}
        </p>
      ) : null}

      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          {bays.data && bays.data.length === 0 ? (
            <EmptyState
              title="Постів ще немає"
              description="Додайте підйомники, ями й стенди — вони стануть колонками дошки."
              action={<Button onClick={() => setPanel({ kind: 'bay' })}>Додати пост</Button>}
            />
          ) : null}

          {bays.data && bays.data.length > 0 ? (
            <div className="overflow-x-auto rounded-bm border border-line bg-surface">
              <div
                className="grid min-w-fit"
                style={{ gridTemplateColumns: `56px repeat(${bays.data.length}, minmax(160px, 1fr))` }}
              >
                <div className="sticky top-0 border-b border-line-strong bg-surface-2" />
                {bays.data.map((bay) => (
                  <div
                    key={bay.id}
                    className="border-b border-l border-line-strong bg-surface-2 px-3 py-2 font-mono text-[11px] font-medium tracking-wider text-ink-faint uppercase"
                  >
                    {bay.name}
                  </div>
                ))}

                <TimeAxis day={day} />
                {bays.data.map((bay) => (
                  <BayColumn
                    key={bay.id}
                    bay={bay}
                    day={day}
                    appointments={(appointments.data ?? []).filter((a) => a.bay_id === bay.id)}
                    selectedId={selected?.id ?? null}
                    onSlot={(startsAt) => setPanel({ kind: 'book', bay, startsAt })}
                    onAppointment={(id) => setPanel({ kind: 'appointment', id })}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </div>

        {panel ? (
          <Card className="sticky top-0 w-80 shrink-0">
            <CardHeader>
              <CardTitle>
                {panel.kind === 'book' ? 'Новий запис' : panel.kind === 'bay' ? 'Новий пост' : 'Запис'}
              </CardTitle>
            </CardHeader>
            <CardBody>
              {panel.kind === 'book' ? (
                <BookingForm
                  key={`${panel.bay.id}-${panel.startsAt.toISOString()}`}
                  bay={panel.bay}
                  startsAt={panel.startsAt}
                  onDone={() => setPanel(null)}
                />
              ) : null}
              {panel.kind === 'appointment' && selected ? (
                <AppointmentCard
                  appointment={selected}
                  bayName={bayName(selected.bay_id)}
                  onClose={() => setPanel(null)}
                />
              ) : null}
              {panel.kind === 'bay' ? (
                <BayForm next={(bays.data?.length ?? 0) * 10 + 10} onDone={() => setPanel(null)} />
              ) : null}
            </CardBody>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function TimeAxis({ day }: { day: Date }) {
  return (
    <div className="relative" style={{ height: HEIGHT }}>
      {slotsOfDay(day)
        .filter((s) => s.getMinutes() === 0)
        .map((slot) => (
          <div
            key={slot.toISOString()}
            className="absolute right-2 -translate-y-1/2 font-mono text-[11px] text-ink-faint tabular"
            style={{ top: minutesFromOpen(slot, day) * PX_PER_MINUTE }}
          >
            {hhmm(slot)}
          </div>
        ))}
    </div>
  );
}

function BayColumn({
  bay,
  day,
  appointments,
  selectedId,
  onSlot,
  onAppointment,
}: {
  bay: Bay;
  day: Date;
  appointments: Appointment[];
  selectedId: string | null;
  onSlot: (startsAt: Date) => void;
  onAppointment: (id: string) => void;
}) {
  const slotHeight = SLOT_MINUTES * PX_PER_MINUTE;

  return (
    <div className="relative border-l border-line" style={{ height: HEIGHT }}>
      {/* Вільні клітинки — кнопки: клавіатурою так само можна записати, як мишею. */}
      {slotsOfDay(day).map((slot) => (
        <button
          key={slot.toISOString()}
          type="button"
          aria-label={`${bay.name}, ${hhmm(slot)} — записати`}
          className={cn(
            'absolute inset-x-0 block border-t text-left hover:bg-accent-soft/40 focus-visible:bg-accent-soft/60',
            slot.getMinutes() === 0 ? 'border-line' : 'border-line/40',
          )}
          style={{ top: minutesFromOpen(slot, day) * PX_PER_MINUTE, height: slotHeight }}
          onClick={() => onSlot(slot)}
        />
      ))}

      {appointments.map((a) => {
        const start = new Date(a.starts_at);
        const end = new Date(a.ends_at);
        const top = Math.max(0, minutesFromOpen(start, day)) * PX_PER_MINUTE;
        const bottom = Math.min(HEIGHT, minutesFromOpen(end, day) * PX_PER_MINUTE);
        if (bottom <= 0 || top >= HEIGHT) return null;
        return (
          <button
            key={a.id}
            type="button"
            onClick={() => onAppointment(a.id)}
            className={cn(
              'absolute inset-x-1 overflow-hidden rounded-bm border-l-4 px-2 py-1 text-left text-xs shadow-sm',
              STATUS_STYLE[a.status],
              selectedId === a.id && 'ring-2 ring-accent',
            )}
            style={{ top, height: Math.max(bottom - top, 22) }}
            title={`${a.customer_name} · ${STATUS_LABEL[a.status]}`}
          >
            <div className="font-medium">
              <span className="tabular">{hhmm(start)}</span> {a.customer_name}
            </div>
            {a.vehicle_label ? <div className="truncate text-ink-muted">{a.vehicle_label}</div> : null}
          </button>
        );
      })}
    </div>
  );
}

const KINDS: { id: BayKind; label: string }[] = [
  { id: 'lift', label: 'Підйомник' },
  { id: 'pit', label: 'Оглядова яма' },
  { id: 'alignment', label: 'Розвал-сходження' },
  { id: 'diagnostics', label: 'Діагностика' },
  { id: 'wash', label: 'Мийка' },
  { id: 'other', label: 'Інше' },
];

function BayForm({ next, onDone }: { next: number; onDone: () => void }) {
  const create = useCreateBay();
  const [name, setName] = useState('');
  const [kind, setKind] = useState<BayKind>('lift');

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    create.mutate({ name: name.trim(), kind, position: next }, { onSuccess: onDone });
  }

  const inputClass = 'h-9 w-full rounded-bm border border-line-strong bg-surface px-3 text-sm text-ink';

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">Назва</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Підйомник 1" className={inputClass} />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">Тип</span>
        <select value={kind} onChange={(e) => setKind(e.target.value as BayKind)} className={inputClass}>
          {KINDS.map((k) => (
            <option key={k.id} value={k.id}>
              {k.label}
            </option>
          ))}
        </select>
      </label>
      {create.error ? (
        <p role="alert" className="rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
          {create.error.message}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button type="submit" disabled={!name.trim() || create.isPending}>
          Додати
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Скасувати
        </Button>
      </div>
    </form>
  );
}
