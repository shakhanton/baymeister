/** «1147.50» → «1 147,50 ₴». Рядок від бекенда не стає числом — копійки не губляться. */
export function formatMoney(value: string | null | undefined): string {
  if (value == null) return '—';
  const [whole = '0', cents = '00'] = value.split('.');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${cents} ₴`;
}

/** «4.500» → «4,5»; «1.000» → «1»; «0.000» → «0». */
export function formatQty(value: string): string {
  const trimmed = value.includes('.') ? value.replace(/0+$/, '').replace(/\.$/, '') : value;
  return trimmed.replace('.', ',') || '0';
}

export const UNIT_LABEL: Record<string, string> = {
  h: 'н/г',
  pcs: 'шт.',
  l: 'л',
  kg: 'кг',
  m: 'м',
  set: 'компл.',
};

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
