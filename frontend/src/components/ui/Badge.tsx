import type { HTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

/**
 * Static variant map -- NOT dynamic class construction.
 *
 * The previous implementation built classes as `bg-${color}-500/10`, which
 * Tailwind cannot see: it scans source files statically and only emits classes
 * it finds as complete literal strings. Those badges rendered with no colour at
 * all. Every variant below is a complete literal so it survives the scan.
 * (MASTER.md §6, first anti-pattern.)
 */
const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-1 text-xs font-semibold tracking-wide transition-colors [&_svg]:size-3.5 [&_svg]:shrink-0',
  {
    variants: {
      /**
       * Backgrounds are OPAQUE (`bg-card`), not translucent tints.
       *
       * `bg-primary/10` composites against whatever sits behind it, so the same
       * badge measured 4.6:1 on a white card but only 3.73:1 on the landing
       * hero's green canvas — a real audit failure, since a token that passes in
       * isolation can still fail once alpha-blended. An opaque surface makes the
       * ratio identical everywhere: text-primary on card is 5.02:1 (light) and
       * 9.81:1 (dark), and the same holds for accent and destructive.
       */
      variant: {
        neutral: 'border-border bg-muted text-muted-foreground',
        primary: 'border-primary/30 bg-card text-primary',
        success: 'border-secondary/40 bg-card text-primary',
        caution: 'border-accent/40 bg-card text-accent',
        risk: 'border-destructive/40 bg-card text-destructive',
        outline: 'border-border-input bg-transparent text-foreground',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
