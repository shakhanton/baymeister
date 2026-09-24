import { cn } from '@baymeister/ui';
import { NavLink } from 'react-router';

/** «850.00» → «850,00 ₴». Рядок від бекенда не перетворюємо на число — копійки не губляться. */
export function formatMoney(value: string | null | undefined): string {
  if (value == null) return '—';
  const [whole = '0', cents = '00'] = value.split('.');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${cents} ₴`;
}

export const UNIT_LABEL = { pcs: 'шт.', l: 'л', kg: 'кг', m: 'м', set: 'компл.' } as const;

/** Дві сторінки одного блоку — роботи й запчастини. */
export function CatalogTabs() {
  const tab = ({ isActive }: { isActive: boolean }) =>
    cn(
      'border-b-2 px-1 pb-2 text-sm transition-colors',
      isActive ? 'border-accent font-medium text-accent' : 'border-transparent text-ink-muted hover:text-ink',
    );
  return (
    <nav className="flex gap-6 border-b border-line" aria-label="Розділи прайсу">
      <NavLink to="/catalog" end className={tab}>
        Роботи
      </NavLink>
      <NavLink to="/catalog/parts" className={tab}>
        Запчастини
      </NavLink>
    </nav>
  );
}

export const inputClass =
  'h-9 w-full rounded-bm border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-faint';

export function Field({
  label,
  error,
  required,
  className,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn('flex flex-col gap-1.5', className)}>
      <span className="text-sm font-medium text-ink">
        {label}
        {required ? <span className="text-danger"> *</span> : null}
      </span>
      {children}
      {error ? <span className="text-xs text-danger">{error}</span> : null}
    </label>
  );
}

export function ErrorNote({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
      {message}
    </p>
  );
}

export function ListSkeleton() {
  return (
    <div className="flex flex-col gap-2" role="status" aria-label="Завантаження">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="h-12 animate-pulse rounded-bm bg-surface-2" />
      ))}
    </div>
  );
}

export const thClass =
  'border-b border-line-strong px-4 py-3 text-left font-mono text-[11px] font-medium tracking-wider text-ink-faint uppercase';

/** Гроші й години з форми: «850», «850,5», «1.35» — як у контракті. */
export const MONEY_RE = /^\d{1,9}([.,]\d{1,2})?$/;
export const HOURS_RE = /^\d{1,3}([.,]\d{1,2})?$/;
