import { Badge, cn } from '@baymeister/ui';
import { NavLink } from 'react-router';
import type { OrderStatus } from '../api';

/** «1147.50» → «1 147,50 ₴». Рядок від бекенда не стає числом — копійки не губляться. */
export function formatMoney(value: string | null | undefined): string {
  if (value == null) return '—';
  const [whole = '0', cents = '00'] = value.split('.');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${cents} ₴`;
}

/** «4.500» → «4,5»; «1.000» → «1»; «0.000» → «0». */
export function formatQty(value: string): string {
  const trimmed = value.includes('.') ? value.replace(/0+$/, '').replace(/\.$/, '') : value;
  return trimmed.replace('.', ',') || '0';
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  // Дата без часу («2026-10-01») — без зсуву поясу.
  const date = value.length === 10 ? new Date(`${value}T12:00:00`) : new Date(value);
  return date.toLocaleDateString('uk-UA');
}

export const UNIT_LABEL: Record<string, string> = {
  pcs: 'шт.',
  l: 'л',
  kg: 'кг',
  m: 'м',
  set: 'компл.',
};

export const MONEY_RE = /^\d{1,9}([.,]\d{1,2})?$/;
export const QTY_RE = /^\d{1,6}([.,]\d{1,3})?$/;

export const STATUS_LABEL: Record<OrderStatus, string> = {
  draft: 'чернетка',
  ordered: 'відправлено',
  received: 'отримано',
  cancelled: 'скасовано',
};

const STATUS_TONE = {
  draft: 'planned',
  ordered: 'wip',
  received: 'ready',
  cancelled: 'neutral',
} as const;

export function StatusBadge({ status }: { status: OrderStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>;
}

/** Три сторінки блоку. Лічильник потреб — щоб їх не пропустили. */
export function ProcurementTabs({ needs }: { needs?: number }) {
  const tab = ({ isActive }: { isActive: boolean }) =>
    cn(
      'border-b-2 px-1 pb-2 text-sm transition-colors',
      isActive ? 'border-accent font-medium text-accent' : 'border-transparent text-ink-muted hover:text-ink',
    );
  return (
    <nav className="flex gap-6 border-b border-line" aria-label="Розділи закупівель">
      <NavLink to="/procurement" end className={tab}>
        Замовлення
      </NavLink>
      <NavLink to="/procurement/needs" className={tab}>
        Потрібно замовити
        {needs ? (
          <Badge tone="danger" className="ml-2">
            {needs}
          </Badge>
        ) : null}
      </NavLink>
      <NavLink to="/procurement/suppliers" className={tab}>
        Постачальники
      </NavLink>
    </nav>
  );
}

export const inputClass =
  'h-9 w-full rounded-bm border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-faint';

export const thClass =
  'border-b border-line-strong px-4 py-3 text-left font-mono text-[11px] font-medium tracking-wider text-ink-faint uppercase';

export function ErrorNote({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
      {message}
    </p>
  );
}
