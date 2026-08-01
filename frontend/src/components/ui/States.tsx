import { useEffect, useState, type ReactNode } from 'react';
import { AlertOctagon, RefreshCw, WifiOff, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from './Button';
import { Reveal } from './Reveal';

/** Shared shell so empty / error / loading states share one silhouette. */
function StateShell({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <Reveal
      className={cn(
        'card-surface flex min-h-[26rem] flex-col items-center justify-center gap-5 p-8 text-center sm:p-12',
        className,
      )}
    >
      {children}
    </Reveal>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <StateShell>
      <div className="relative">
        {/* Decorative pulse ring - conveys "ready and waiting", not progress. */}
        <span
          className="absolute inset-0 rounded-xl bg-primary/20 animate-pulse-ring motion-reduce:hidden"
          aria-hidden="true"
        />
        <div className="relative grid size-20 place-items-center rounded-xl border border-primary/20 bg-primary/10">
          <Icon className="size-9 text-primary" aria-hidden="true" />
        </div>
      </div>
      <div className="max-w-md space-y-2">
        <h2 className="text-h2 text-foreground">{title}</h2>
        <p className="text-base leading-relaxed text-muted-foreground">{description}</p>
      </div>
      {children}
    </StateShell>
  );
}

export function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  isOffline,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  isOffline?: boolean;
}) {
  const Icon = isOffline ? WifiOff : AlertOctagon;
  return (
    <StateShell className="border-destructive/25">
      <div className="grid size-20 place-items-center rounded-xl border border-destructive/20 bg-destructive/10">
        <Icon className="size-9 text-destructive" aria-hidden="true" />
      </div>
      {/* role=alert so the failure is announced, not just shown in red. */}
      <div className="max-w-md space-y-2" role="alert">
        <h2 className="text-h2 text-destructive">{title}</h2>
        <p className="text-base leading-relaxed text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button onClick={onRetry} variant="outline">
          <RefreshCw aria-hidden="true" />
          Try again
        </Button>
      )}
    </StateShell>
  );
}

/**
 * Staged loader.
 *
 * Ensemble inference here can take several seconds. An indefinite spinner over
 * that duration reads as a hang, so this advances through the real pipeline
 * stages. The stages are descriptive of actual backend work, and the final
 * stage intentionally does not auto-complete -- it holds until the request
 * resolves rather than implying finished work that hasn't happened.
 */
export function StagedLoader({
  stages,
  title = 'Working…',
  intervalMs = 1400,
}: {
  stages: string[];
  title?: string;
  intervalMs?: number;
}) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (index >= stages.length - 1) return;
    const timer = setTimeout(() => setIndex((i) => i + 1), intervalMs);
    return () => clearTimeout(timer);
  }, [index, stages.length, intervalMs]);

  return (
    <StateShell>
      <div className="relative grid size-20 place-items-center">
        <span
          className="absolute inset-0 rounded-full border-4 border-primary/15 border-t-primary motion-safe:animate-spin"
          aria-hidden="true"
        />
        <span className="tabular text-sm font-bold text-primary">
          {Math.round(((index + 1) / stages.length) * 100)}%
        </span>
      </div>

      {/* aria-live=polite announces each stage without interrupting. */}
      <div className="space-y-3" aria-live="polite" aria-busy="true">
        <h2 className="text-h3 text-foreground">{title}</h2>
        <ul className="space-y-2 text-left">
          {stages.map((stage, i) => (
            <li
              key={stage}
              className={cn(
                'flex items-center gap-2.5 text-sm transition-colors duration-300',
                i < index && 'text-muted-foreground',
                i === index && 'font-medium text-foreground',
                i > index && 'text-muted-foreground/50',
              )}
            >
              <span
                className={cn(
                  'size-1.5 shrink-0 rounded-full transition-colors duration-300',
                  i <= index ? 'bg-primary' : 'bg-muted-foreground/30',
                )}
                aria-hidden="true"
              />
              {stage}
            </li>
          ))}
        </ul>
      </div>
    </StateShell>
  );
}
