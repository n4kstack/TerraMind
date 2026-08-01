import { createContext, forwardRef, useContext, useId, type InputHTMLAttributes, type ReactNode } from 'react';
import * as LabelPrimitive from '@radix-ui/react-label';
import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Accessible form field wrapper.
 *
 * This exists so that the accessible wiring cannot be forgotten. It generates
 * one id and threads it through label/control/description/error, sets
 * aria-describedby and aria-invalid automatically, and renders errors adjacent
 * to their field with role="alert" (MASTER.md §6: errors must never be
 * collected at the top of a form, and must never be colour-only).
 */

interface FieldContextValue {
  id: string;
  descriptionId: string;
  errorId: string;
  hasError: boolean;
  hasDescription: boolean;
}

const FieldContext = createContext<FieldContextValue | null>(null);

function useFieldContext() {
  const ctx = useContext(FieldContext);
  if (!ctx) throw new Error('Field subcomponents must be used within <Field>');
  return ctx;
}

export function Field({
  children,
  error,
  description,
  className,
}: {
  children: ReactNode;
  error?: string | null;
  description?: string;
  className?: string;
}) {
  const id = useId();
  const value: FieldContextValue = {
    id,
    descriptionId: `${id}-description`,
    errorId: `${id}-error`,
    hasError: Boolean(error),
    hasDescription: Boolean(description),
  };

  return (
    <FieldContext.Provider value={value}>
      <div className={cn('space-y-1.5', className)}>
        {children}
        {description && !error && (
          <p id={value.descriptionId} className="text-xs text-muted-foreground">
            {description}
          </p>
        )}
        {error && (
          <p
            id={value.errorId}
            role="alert"
            className="flex items-center gap-1.5 text-xs font-medium text-destructive"
          >
            {/* Icon + text, never colour alone. */}
            <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
            {error}
          </p>
        )}
      </div>
    </FieldContext.Provider>
  );
}

export function FieldLabel({
  children,
  className,
  optional,
}: {
  children: ReactNode;
  className?: string;
  optional?: boolean;
}) {
  const { id } = useFieldContext();
  return (
    <LabelPrimitive.Root
      htmlFor={id}
      className={cn('flex items-center gap-1.5 text-label text-foreground', className)}
    >
      {children}
      {optional && <span className="font-normal text-muted-foreground">(optional)</span>}
    </LabelPrimitive.Root>
  );
}

/** Wire arbitrary controls (e.g. Combobox) into the field's a11y contract. */
// eslint-disable-next-line react-refresh/only-export-components
export function useFieldControlProps() {
  const { id, descriptionId, errorId, hasError, hasDescription } = useFieldContext();
  const describedBy = [hasDescription && !hasError ? descriptionId : null, hasError ? errorId : null]
    .filter(Boolean)
    .join(' ');
  return {
    id,
    'aria-invalid': hasError || undefined,
    'aria-describedby': describedBy || undefined,
  };
}

export const inputClassName = cn(
  'flex h-11 w-full rounded-md border border-border-input bg-card px-3.5 py-2',
  // 16px minimum: anything smaller makes iOS Safari zoom on focus.
  'text-base text-foreground placeholder:text-muted-foreground',
  'transition-[border-color,box-shadow] duration-150 ease-out',
  'focus-visible:outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25',
  'disabled:cursor-not-allowed disabled:opacity-60',
  'aria-[invalid=true]:border-destructive aria-[invalid=true]:focus-visible:ring-destructive/25',
);

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    const fieldProps = useFieldControlProps();
    return <input ref={ref} className={cn(inputClassName, className)} {...fieldProps} {...props} />;
  },
);

/** Numeric input with a unit suffix, for soil/climate parameters. */
export const NumericInput = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { unit?: string }
>(function NumericInput({ className, unit, ...props }, ref) {
  const fieldProps = useFieldControlProps();
  return (
    <div className="relative">
      <input
        ref={ref}
        type="number"
        inputMode="decimal"
        className={cn(inputClassName, 'tabular pr-14', className)}
        {...fieldProps}
        {...props}
      />
      {unit && (
        <span
          className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-xs font-medium text-muted-foreground"
          aria-hidden="true"
        >
          {unit}
        </span>
      )}
    </div>
  );
});
