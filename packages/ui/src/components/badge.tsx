import { cva, type VariantProps } from 'class-variance-authority';
import type { HTMLAttributes } from 'react';
import { cn } from '../lib/cn';

const badge = cva(
  'inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wide whitespace-nowrap',
  {
    variants: {
      tone: {
        neutral: 'bg-surface-2 text-ink-muted',
        accent: 'bg-accent-soft text-accent',
        ready: 'bg-ready-soft text-ready',
        wip: 'bg-wip-soft text-wip',
        planned: 'bg-planned-soft text-planned',
        danger: 'bg-danger-soft text-danger',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badge> {}

export function Badge({ tone, className, ...props }: BadgeProps) {
  return <span className={cn(badge({ tone }), className)} {...props} />;
}
