/**
 * Час на дошці — місцевий час браузера. На бекенд іде ISO з поясом
 * (toISOString дає UTC із «Z»), тож «10:00 у Києві» ніде не стане «10:00 UTC».
 */

export const DAY_START_HOUR = 8;
export const DAY_END_HOUR = 20;
export const SLOT_MINUTES = 30;
export const PX_PER_MINUTE = 1.2;

export function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

export function addMinutes(date: Date, minutes: number): Date {
  return new Date(date.getTime() + minutes * 60_000);
}

/** Хвилини від початку видимої частини дня (08:00) — для позиції на дошці. */
export function minutesFromOpen(value: Date, day: Date): number {
  const open = new Date(day);
  open.setHours(DAY_START_HOUR, 0, 0, 0);
  return (value.getTime() - open.getTime()) / 60_000;
}

export function hhmm(value: Date | string): string {
  return new Date(value).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
}

/** 'YYYY-MM-DD' у місцевому часі — для <input type="date"> і URL. */
export function isoDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function parseIsoDate(value: string | null): Date {
  const match = value?.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return startOfDay(new Date());
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

export function slotsOfDay(day: Date): Date[] {
  const slots: Date[] = [];
  const cursor = new Date(day);
  cursor.setHours(DAY_START_HOUR, 0, 0, 0);
  while (cursor.getHours() < DAY_END_HOUR) {
    slots.push(new Date(cursor));
    cursor.setMinutes(cursor.getMinutes() + SLOT_MINUTES);
  }
  return slots;
}
