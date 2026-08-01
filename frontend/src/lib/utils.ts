import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind classes, resolving conflicts so the last one wins.
 * Required for variant components where a caller's `className` must be able to
 * override a variant's default (e.g. `<Button className="bg-accent">`).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Clamp a number into a range. */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Format a confidence score (0-1 or 0-100) as a whole percentage.
 * Backends in this project are inconsistent about which scale they return, so
 * values <= 1 are treated as fractions.
 */
export function formatConfidence(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  const pct = value <= 1 ? value * 100 : value;
  return `${Math.round(clamp(pct, 0, 100))}%`;
}

/** Title-case a snake_case or kebab-case key for display. */
export function humanize(key: string): string {
  return key
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}
