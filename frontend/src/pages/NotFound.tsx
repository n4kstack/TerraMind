import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { NAV_ITEMS } from '@/components/layout/navigation';

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-6 py-16 text-center">
      <span className="grid size-20 place-items-center rounded-xl bg-muted text-muted-foreground">
        <Compass className="size-9" aria-hidden="true" />
      </span>

      <div className="space-y-2">
        <h1 className="text-h1 text-foreground">This page doesn't exist</h1>
        <p className="text-base leading-relaxed text-muted-foreground">
          The link may be out of date. Here's everything TerraMind can do:
        </p>
      </div>

      <ul className="grid w-full gap-2 sm:grid-cols-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, description }) => (
          <li key={to}>
            <Link
              to={to}
              className="flex h-full items-start gap-3 rounded-lg border border-border bg-card p-4 text-left transition-colors duration-150 hover:border-primary/30 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="block font-semibold text-foreground">{label}</span>
                <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">
                  {description}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <Button asChild variant="outline">
        <Link to="/">Back to home</Link>
      </Button>
    </div>
  );
}
