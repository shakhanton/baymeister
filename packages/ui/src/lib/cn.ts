import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Склеює класи і гасить конфлікти Tailwind: cn('p-2', cond && 'p-4') -> 'p-4'. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
