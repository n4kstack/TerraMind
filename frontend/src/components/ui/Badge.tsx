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
       * hero's canvas — a real audit failure, since a token that passes in
       * isolation can still fail once alpha-blended. An opaque surface makes the
       * ratio identical everywhere: text-primary on card is 6.52:1 (light) and
       * 8.35:1 (dark), and the same holds for secondary, accent and destructive.
       *
       * `success` draws its text from --secondary, not --primary, and that is
       * load-bearing rather than cosmetic. Primary is the harvest ochre the
       * whole brand is built on; caution is a gold. Once both are warm they sit
       * 16 degrees of hue apart and measured dE 21.9 — below the 25 this
       * project treats as "obviously a different colour" — so a success chip and
       * a caution chip became near-indistinguishable. On a tool that tells a
       * smallholder how much to trust a yield forecast before buying seed, that
       * is a correctness bug, not a style one. --secondary stays green for
       * exactly this reason; see MASTER.md 1.4 and check-contrast.py.
       */
      variant: {
        neutral: 'border-border bg-muted text-muted-foreground',
        primary: 'border-primary/30 bg-card text-primary',
        success: 'border-secondary/40 bg-card text-secondary',
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
