import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

/**
 * In dark mode our shadows are effectively invisible against a near-black
 * surface, so elevation is carried by border contrast instead. That is why the
 * `elevated` variant bumps the border rather than only the shadow.
 */
export const Card = forwardRef<
  HTMLDivElement,
  HTMLAttributes<HTMLDivElement> & { interactive?: boolean; elevated?: boolean }
>(function Card({ className, interactive, elevated, ...props }, ref) {
  return (
    <div
      ref={ref}
      className={cn(
        'rounded-lg border border-border bg-card text-card-foreground',
        elevated ? 'shadow-md dark:border-border/80' : 'shadow-sm',
        interactive && [
          'cursor-pointer transition-[box-shadow,border-color,transform] duration-200 ease-organic',
          'hover:-translate-y-0.5 hover:shadow-lg hover:border-primary/30',
          'focus-within:border-primary/40',
        ],
        className,
      )}
      {...props}
    />
  );
});

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function CardHeader({ className, ...props }, ref) {
    return <div ref={ref} className={cn('flex flex-col gap-1.5 p-5 sm:p-6', className)} {...props} />;
  },
);

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  function CardTitle({ className, ...props }, ref) {
    return <h3 ref={ref} className={cn('text-h3 tracking-tight', className)} {...props} />;
  },
);

export const CardDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  function CardDescription({ className, ...props }, ref) {
    return <p ref={ref} className={cn('text-sm text-muted-foreground', className)} {...props} />;
  },
);

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function CardContent({ className, ...props }, ref) {
    return <div ref={ref} className={cn('p-5 pt-0 sm:p-6 sm:pt-0', className)} {...props} />;
  },
);

export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function CardFooter({ className, ...props }, ref) {
    return (
      <div
        ref={ref}
        className={cn('flex items-center gap-3 border-t border-border p-5 sm:p-6', className)}
        {...props}
      />
    );
  },
);
