import { useEffect, useMemo, useRef, useState } from 'react';
import * as Popover from '@radix-ui/react-popover';
import { Check, ChevronsUpDown, Search, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFieldControlProps, inputClassName } from './Field';

/**
 * Searchable single-select.
 *
 * A native <select> was rejected deliberately: this app has 719 districts with
 * up to 75 in a single state, and scrolling that in a native picker on a phone
 * is miserable. Type-to-filter is the difference between usable and not.
 *
 * Implements the ARIA combobox pattern manually rather than pulling in cmdk:
 * role=combobox trigger, role=listbox popup, roving aria-activedescendant,
 * Up/Down/Home/End/Enter/Escape handling.
 */
export interface ComboboxProps {
  options: string[];
  value: string | null;
  onChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  /**
   * Formats an option for DISPLAY only; `onChange` still emits the raw value.
   * The backend returns states and districts lowercased ("andhra pradesh"),
   * and the models were trained on that exact casing — so the payload must
   * keep it while the UI shows something presentable.
   */
  formatLabel?: (value: string) => string;
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  emptyMessage = 'No matches found',
  disabled,
  loading,
  className,
  formatLabel,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const fieldProps = useFieldControlProps();

  const label = useMemo(() => formatLabel ?? ((v: string) => v), [formatLabel]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    // Prefix matches first - typing "Nor" should surface "North 24 Parganas"
    // above "Greater Noida".
    const starts: string[] = [];
    const contains: string[] = [];
    for (const opt of options) {
      const lower = label(opt).toLowerCase();
      if (lower.startsWith(q)) starts.push(opt);
      else if (lower.includes(q)) contains.push(opt);
    }
    return [...starts, ...contains];
  }, [options, query, label]);

  // Reset the highlight whenever the result set changes, otherwise the active
  // index can point past the end of a newly-filtered list.
  useEffect(() => setActiveIndex(0), [query, options]);

  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  // Keep the highlighted option in view during keyboard navigation.
  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex, open]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (filtered.length === 0) return;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((i) => (i + 1) % filtered.length);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((i) => (i - 1 + filtered.length) % filtered.length);
        break;
      case 'Home':
        e.preventDefault();
        setActiveIndex(0);
        break;
      case 'End':
        e.preventDefault();
        setActiveIndex(filtered.length - 1);
        break;
      case 'Enter': {
        e.preventDefault();
        const selected = filtered[activeIndex];
        if (selected) {
          onChange(selected);
          setOpen(false);
        }
        break;
      }
    }
  }

  const listboxId = `${fieldProps.id}-listbox`;

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-controls={open ? listboxId : undefined}
          aria-haspopup="listbox"
          disabled={disabled || loading}
          className={cn(
            inputClassName,
            'cursor-pointer items-center justify-between gap-2 text-left',
            !value && 'text-muted-foreground',
            className,
          )}
          {...fieldProps}
        >
          <span className="truncate">{value ? label(value) : placeholder}</span>
          {loading ? (
            <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" aria-hidden="true" />
          ) : (
            <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          )}
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          className={cn(
            'z-50 w-[var(--radix-popover-trigger-width)] overflow-hidden rounded-md border border-border bg-card shadow-lg',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0',
            'data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95',
            'data-[side=bottom]:slide-in-from-top-1 data-[side=top]:slide-in-from-bottom-1',
          )}
          onOpenAutoFocus={(e) => {
            // Focus the search box, not the first option.
            e.preventDefault();
            (e.currentTarget as HTMLElement)
              .querySelector<HTMLInputElement>('input')
              ?.focus();
          }}
        >
          <div className="flex items-center gap-2 border-b border-border px-3">
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              aria-controls={listboxId}
              aria-activedescendant={
                filtered.length > 0 ? `${listboxId}-opt-${activeIndex}` : undefined
              }
              className="h-11 w-full bg-transparent text-base outline-none placeholder:text-muted-foreground"
            />
          </div>

          <div
            ref={listRef}
            id={listboxId}
            role="listbox"
            aria-label={placeholder}
            className="max-h-64 overflow-y-auto overscroll-contain p-1.5"
          >
            {filtered.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">{emptyMessage}</p>
            ) : (
              filtered.map((option, index) => {
                const isSelected = option === value;
                const isActive = index === activeIndex;
                return (
                  <div
                    key={option}
                    id={`${listboxId}-opt-${index}`}
                    data-index={index}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => {
                      onChange(option);
                      setOpen(false);
                    }}
                    onMouseEnter={() => setActiveIndex(index)}
                    className={cn(
                      'flex cursor-pointer items-center justify-between gap-2 rounded-sm px-3 py-2.5 text-sm transition-colors duration-100',
                      isActive ? 'bg-primary/10 text-primary' : 'text-foreground',
                    )}
                  >
                    <span className="truncate">{label(option)}</span>
                    {isSelected && <Check className="size-4 shrink-0 text-primary" aria-hidden="true" />}
                  </div>
                );
              })
            )}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
