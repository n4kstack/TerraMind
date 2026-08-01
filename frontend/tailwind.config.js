import typography from '@tailwindcss/typography';
import animate from 'tailwindcss-animate';

/**
 * TerraMind design tokens.
 * Source of truth: design-system/terramind/MASTER.md
 *
 * Colours are HSL triplets in CSS variables (not hex) so that Tailwind's
 * opacity modifiers work: `bg-primary/10` compiles to
 * `hsl(var(--primary) / 0.1)`. A hex variable would silently break that.
 */

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background) / <alpha-value>)',
        foreground: 'hsl(var(--foreground) / <alpha-value>)',
        card: {
          DEFAULT: 'hsl(var(--card) / <alpha-value>)',
          foreground: 'hsl(var(--card-foreground) / <alpha-value>)',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary) / <alpha-value>)',
          foreground: 'hsl(var(--primary-foreground) / <alpha-value>)',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary) / <alpha-value>)',
          foreground: 'hsl(var(--secondary-foreground) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent) / <alpha-value>)',
          foreground: 'hsl(var(--accent-foreground) / <alpha-value>)',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted) / <alpha-value>)',
          foreground: 'hsl(var(--muted-foreground) / <alpha-value>)',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive) / <alpha-value>)',
          foreground: 'hsl(var(--destructive-foreground) / <alpha-value>)',
        },
        border: 'hsl(var(--border) / <alpha-value>)',
        // Distinct from `border`: used where the boundary IS the affordance
        // (inputs, comboboxes) and must therefore clear WCAG 1.4.11 at 3:1.
        'border-input': 'hsl(var(--border-input) / <alpha-value>)',
        ring: 'hsl(var(--ring) / <alpha-value>)',
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '16px',
        xl: '24px',
        organic: '28px 24px 26px 22px',
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans Variable"', 'Plus Jakarta Sans', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        display: ['3.5rem', { lineHeight: '1.05', letterSpacing: '-0.03em', fontWeight: '800' }],
        h1: ['2.25rem', { lineHeight: '1.15', letterSpacing: '-0.02em', fontWeight: '700' }],
        h2: ['1.5rem', { lineHeight: '1.25', letterSpacing: '-0.01em', fontWeight: '700' }],
        h3: ['1.125rem', { lineHeight: '1.4', fontWeight: '600' }],
        label: ['0.8125rem', { lineHeight: '1.4', fontWeight: '600' }],
      },
      boxShadow: {
        sm: '0 1px 2px rgba(8,19,13,0.04)',
        md: '0 4px 16px rgba(8,19,13,0.06)',
        lg: '0 12px 32px rgba(8,19,13,0.08)',
        xl: '0 24px 56px rgba(8,19,13,0.10)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        'pulse-ring': {
          '0%': { transform: 'scale(0.95)', opacity: '0.5' },
          '70%': { transform: 'scale(1.6)', opacity: '0' },
          '100%': { transform: 'scale(1.6)', opacity: '0' },
        },
        sway: {
          '0%, 100%': { transform: 'rotate(-1.5deg)' },
          '50%': { transform: 'rotate(1.5deg)' },
        },
        /* Landing aurora. Percentage translations keep each blob's travel
           proportional to its own size, so the field composes the same way at
           every viewport width. */
        'drift-a': {
          '0%, 100%': { transform: 'translate3d(0, 0, 0) scale(1)' },
          '50%': { transform: 'translate3d(7%, 5%, 0) scale(1.16)' },
        },
        'drift-b': {
          '0%, 100%': { transform: 'translate3d(0, 0, 0) scale(1.1)' },
          '50%': { transform: 'translate3d(-6%, 8%, 0) scale(0.92)' },
        },
        'drift-c': {
          '0%, 100%': { transform: 'translate3d(0, 0, 0) scale(0.94)' },
          '50%': { transform: 'translate3d(8%, -6%, 0) scale(1.14)' },
        },
        'aurora-wash': {
          '0%, 100%': { opacity: '0.35', transform: 'translate3d(-4%, 0, 0)' },
          '50%': { opacity: '0.8', transform: 'translate3d(4%, 0, 0)' },
        },
        'mote-rise': {
          '0%': { transform: 'translate3d(0, 0, 0)', opacity: '0' },
          '15%, 70%': { opacity: '1' },
          '100%': { transform: 'translate3d(18px, -160px, 0)', opacity: '0' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 250ms cubic-bezier(0.22,1,0.36,1)',
        'accordion-up': 'accordion-up 200ms cubic-bezier(0.22,1,0.36,1)',
        shimmer: 'shimmer 1.8s infinite',
        'pulse-ring': 'pulse-ring 2.4s cubic-bezier(0.22,1,0.36,1) infinite',
        sway: 'sway 6s ease-in-out infinite',
        // Long and mutually prime enough that the field never visibly repeats.
        'drift-a': 'drift-a 34s cubic-bezier(0.45,0,0.55,1) infinite',
        'drift-b': 'drift-b 42s cubic-bezier(0.45,0,0.55,1) infinite',
        'drift-c': 'drift-c 38s cubic-bezier(0.45,0,0.55,1) infinite',
        'aurora-wash': 'aurora-wash 26s ease-in-out infinite',
        // Duration and delay are overridden per mote inline.
        'mote-rise': 'mote-rise 24s linear infinite',
      },
      transitionTimingFunction: {
        organic: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [typography, animate],
};
