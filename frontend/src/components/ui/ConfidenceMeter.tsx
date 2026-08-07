import { motion } from 'framer-motion';
import { CheckCircle2, AlertTriangle, Info } from 'lucide-react';
import { cn, clamp } from '@/lib/utils';
import { EASE_ORGANIC } from '@/lib/motion';

/**
 * Every model output in TerraMind must carry a confidence indicator
 * (MASTER.md §5.1). Predictions drive real planting and spending decisions, so
 * presenting one as a bare certainty is a product-level failure, not a styling
 * choice.
 *
 * Confidence is conveyed three ways -- bar length, colour, and an explicit
 * text band -- because colour alone fails for colourblind users and washes out
 * on a phone screen in direct sunlight.
 */

type Band = 'high' | 'moderate' | 'low';

function bandFor(pct: number): Band {
  if (pct >= 75) return 'high';
  if (pct >= 50) return 'moderate';
  return 'low';
}

/**
 * The three bands must be tellable apart at a glance, which is why `high` reads
 * from --secondary rather than --primary.
 *
 * Primary is the brand's harvest ochre and accent is a gold; side by side they
 * measured dE 21.9 in light mode, under the 25 this project treats as clearly
 * distinct. A confidence meter whose "high" and "moderate" look the same defeats
 * the entire point of showing confidence — this component exists because a
 * model output presented as a bare certainty is a product-level failure, and a
 * band nobody can read is the same failure wearing a progress bar.
 *
 * --secondary is green and stays green for this. The icon and the label carry
 * the meaning independently anyway (never hue alone — MASTER.md 1.4), but the
 * colour should not actively mislead.
 */
const BAND_META: Record<Band, { label: string; bar: string; text: string; Icon: typeof Info }> = {
  high: { label: 'High confidence', bar: 'bg-secondary', text: 'text-secondary', Icon: CheckCircle2 },
  moderate: { label: 'Moderate confidence', bar: 'bg-accent', text: 'text-accent', Icon: AlertTriangle },
  low: { label: 'Low confidence', bar: 'bg-destructive', text: 'text-destructive', Icon: Info },
};

export function ConfidenceMeter({
  value,
  className,
  showLabel = true,
  size = 'md',
}: {
  /** Accepts 0-1 or 0-100; values <= 1 are treated as fractions. */
  value: number;
  className?: string;
  showLabel?: boolean;
  size?: 'sm' | 'md';
}) {
  const pct = clamp(value <= 1 ? value * 100 : value, 0, 100);
  const rounded = Math.round(pct);
  const band = bandFor(pct);
  const { label, bar, text, Icon } = BAND_META[band];

  return (
    <div className={cn('space-y-1.5', className)}>
      {showLabel && (
        <div className="flex items-center justify-between gap-2">
          <span className={cn('flex items-center gap-1.5 text-xs font-semibold', text)}>
            <Icon className="size-3.5 shrink-0" aria-hidden="true" />
            {label}
          </span>
          <span className="tabular text-xs font-bold text-foreground">{rounded}%</span>
        </div>
      )}
      <div
        role="meter"
        aria-valuenow={rounded}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${rounded} percent`}
        className={cn('w-full overflow-hidden rounded-sm bg-muted', size === 'sm' ? 'h-1.5' : 'h-2.5')}
      >
        <motion.div
          className={cn('h-full rounded-sm', bar)}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: pct / 100 }}
          style={{ originX: 0 }}
          transition={{ duration: 0.7, ease: EASE_ORGANIC }}
        />
      </div>
    </div>
  );
}
