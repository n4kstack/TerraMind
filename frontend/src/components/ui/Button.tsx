import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Sizing note: the default height is 44px, not the more common 36-40px.
 * This audience uses phones outdoors, sometimes with gloves. 44x44 is the
 * documented minimum touch target (MASTER.md §5.5) and it is the default here
 * so that hitting the accessible size is the path of least resistance.
 */
const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md',
    'font-semibold cursor-pointer select-none',
    'transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-out',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
    'disabled:pointer-events-none disabled:opacity-50',
    // Press feedback via transform only - never animate size or margin.
    'active:scale-[0.98]',
    '[&_svg]:pointer-events-none [&_svg]:shrink-0',
  ],
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90',
        accent: 'bg-accent text-accent-foreground shadow-sm hover:bg-accent/90',
        secondary: 'bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/90',
        outline:
          'border border-border-input bg-card text-foreground hover:bg-muted hover:text-foreground',
        ghost: 'text-foreground hover:bg-muted',
        destructive:
          'bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-10 px-3.5 text-sm [&_svg]:size-4',
        md: 'h-11 px-5 text-sm [&_svg]:size-4',
        lg: 'h-12 px-7 text-base [&_svg]:size-5',
        xl: 'h-14 px-8 text-base [&_svg]:size-5',
        icon: 'h-11 w-11 [&_svg]:size-5',
      },
      fullWidth: { true: 'w-full' },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  /** Announced to screen readers while `loading`. */
  loadingText?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, fullWidth, asChild = false, loading = false, loadingText, children, disabled, ...props },
  ref,
) {
  // Slot cannot host the extra spinner element, so `asChild` renders children
  // untouched and simply forwards styling.
  const Comp = asChild ? Slot : 'button';

  return (
    <Comp
      ref={ref}
      className={cn(buttonVariants({ variant, size, fullWidth }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {loading && <Loader2 className="animate-spin" aria-hidden="true" />}
          {loading && loadingText ? loadingText : children}
          {loading && !loadingText && <span className="sr-only">Loading</span>}
        </>
      )}
    </Comp>
  );
});

export { buttonVariants };
