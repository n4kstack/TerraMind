import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

/**
 * Skeletons must occupy the same box as the content they stand in for,
 * otherwise swapping them out shifts layout and blows the CLS budget.
 * Always give them an explicit height.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('skeleton', className)} aria-hidden="true" {...props} />;
}

/** Result-card placeholder used while inference is running. */
export function SkeletonCard() {
  return (
    <div className="card-surface space-y-4 p-6" aria-hidden="true">
      <div className="flex items-center gap-3">
        <Skeleton className="h-12 w-12 rounded-md" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
      <Skeleton className="h-2.5 w-full rounded-sm" />
      <div className="grid grid-cols-2 gap-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    </div>
  );
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cn('h-3.5', i === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  );
}
