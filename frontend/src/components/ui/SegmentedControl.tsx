import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

/**
 * Replaces the previous mode selector, which built its active styles as
 * `bg-${m.color}-500/20 ring-${m.color}-500/30`. Tailwind never emitted those
 * classes, so the selected mode was visually indistinguishable from the
 * unselected ones. Here the active treatment is a single static class plus a
 * shared-layout indicator, so there is nothing for the scanner to miss.
 *
 * Implemented as a radiogroup rather than buttons so arrow keys move between
 * options and screen readers announce the selected state.
 */
export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  hint?: string;
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
}) {
  function handleKeyDown(e: React.KeyboardEvent, index: number) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const delta = e.key === 'ArrowRight' ? 1 : -1;
    const next = options[(index + delta + options.length) % options.length];
    if (next) onChange(next.value);
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn('flex gap-1 rounded-md bg-muted p-1', className)}
    >
      {options.map((option, index) => {
        const isActive = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            tabIndex={isActive ? 0 : -1}
            title={option.hint}
            onClick={() => onChange(option.value)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={cn(
              'relative flex-1 cursor-pointer rounded-sm px-3 py-2.5 text-sm font-semibold',
              'transition-colors duration-150',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
              isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {isActive && (
              <motion.span
                layoutId={`segmented-${label}`}
                className="absolute inset-0 -z-10 rounded-sm bg-card shadow-sm"
                transition={{ type: 'spring', stiffness: 400, damping: 34 }}
              />
            )}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
