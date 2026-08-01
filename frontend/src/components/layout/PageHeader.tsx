import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Reveal } from '@/components/ui/Reveal';

/** Consistent module header so all four pages share one silhouette. */
export function PageHeader({
  icon: Icon,
  title,
  description,
  actions,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <Reveal as="header" className="mb-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <span className="grid size-12 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
            <Icon className="size-6" aria-hidden="true" />
          </span>
          <div className="space-y-1">
            <h1 className="text-h1 text-foreground">{title}</h1>
            <p className="max-w-2xl text-base leading-relaxed text-muted-foreground">{description}</p>
          </div>
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </Reveal>
  );
}
