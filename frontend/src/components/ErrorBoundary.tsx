import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertOctagon, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Catches render-time crashes so a failure in one module shows a recoverable
 * message instead of a blank white page. Still a class component because React
 * provides no hook equivalent for componentDidCatch.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep the component stack in the console for debugging; there is no error
    // reporting backend in this project to forward it to.
    console.error('Unhandled UI error:', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="grid min-h-dvh place-items-center p-6">
        <div className="card-surface w-full max-w-md space-y-5 p-8 text-center">
          <div className="mx-auto grid size-16 place-items-center rounded-xl border border-destructive/20 bg-destructive/10">
            <AlertOctagon className="size-8 text-destructive" aria-hidden="true" />
          </div>
          <div className="space-y-2" role="alert">
            <h1 className="text-h2 text-foreground">This screen stopped responding</h1>
            <p className="text-sm text-muted-foreground">
              Something went wrong while rendering TerraMind. Reloading usually clears it.
            </p>
          </div>
          <pre className="max-h-28 overflow-auto rounded-md bg-muted p-3 text-left text-xs text-muted-foreground">
            {error.message}
          </pre>
          <Button onClick={() => window.location.reload()} fullWidth>
            <RotateCcw aria-hidden="true" />
            Reload TerraMind
          </Button>
        </div>
      </div>
    );
  }
}
