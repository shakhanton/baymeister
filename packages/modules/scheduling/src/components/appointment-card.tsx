import { Badge, Button } from '@baymeister/ui';
import { useChangeStatus, type Appointment, type AppointmentStatus } from '../api';
import { hhmm } from '../time';

export const STATUS_LABEL: Record<AppointmentStatus, string> = {
  booked: 'записаний',
  arrived: 'приїхав',
  completed: 'завершено',
  cancelled: 'скасовано',
  no_show: 'не приїхав',
};

/** Те саме, що дозволяє бекенд. Кнопок недозволених переходів просто немає. */
const ACTIONS: Record<AppointmentStatus, { to: AppointmentStatus; label: string; primary?: boolean }[]> = {
  booked: [
    { to: 'arrived', label: 'Приїхав', primary: true },
    { to: 'no_show', label: 'Не приїхав' },
    { to: 'cancelled', label: 'Скасувати' },
  ],
  arrived: [
    { to: 'completed', label: 'Завершити', primary: true },
    { to: 'cancelled', label: 'Скасувати' },
  ],
  completed: [],
  cancelled: [],
  no_show: [],
};

export function AppointmentCard({
  appointment,
  bayName,
  onClose,
}: {
  appointment: Appointment;
  bayName: string;
  onClose: () => void;
}) {
  const change = useChangeStatus(appointment.id);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <div className="font-cond text-lg leading-tight font-semibold text-ink">
            {appointment.customer_name}
          </div>
          <div className="font-mono text-xs text-ink-muted">{appointment.customer_phone}</div>
        </div>
        <Badge tone={appointment.status === 'booked' ? 'accent' : 'neutral'}>
          {STATUS_LABEL[appointment.status]}
        </Badge>
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        <dt className="text-ink-faint">Пост</dt>
        <dd className="text-ink">{bayName}</dd>
        <dt className="text-ink-faint">Час</dt>
        <dd className="tabular text-ink">
          {hhmm(appointment.starts_at)}–{hhmm(appointment.ends_at)}
        </dd>
        <dt className="text-ink-faint">Авто</dt>
        <dd className="text-ink">{appointment.vehicle_label ?? '—'}</dd>
        {appointment.note ? (
          <>
            <dt className="text-ink-faint">Примітка</dt>
            <dd className="text-ink">{appointment.note}</dd>
          </>
        ) : null}
      </dl>

      {change.error ? (
        <p role="alert" className="rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
          {change.error.message}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {ACTIONS[appointment.status].map((action) => (
          <Button
            key={action.to}
            variant={action.primary ? 'primary' : 'outline'}
            size="sm"
            disabled={change.isPending}
            onClick={() => change.mutate(action.to)}
          >
            {action.label}
          </Button>
        ))}
        <Button variant="ghost" size="sm" className="ml-auto" onClick={onClose}>
          Закрити
        </Button>
      </div>
    </div>
  );
}
