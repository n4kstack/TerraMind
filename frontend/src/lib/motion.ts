import type { Variants, Transition } from 'framer-motion';

/**
 * Shared motion language.
 * Source of truth: design-system/terramind/MASTER.md §4
 *
 * Two hard rules enforced here:
 *  1. Only `transform` and `opacity` are animated. Animating width/height/top
 *     forces layout on every frame and destroys scroll performance on the
 *     mid-range Android devices this audience actually uses.
 *  2. Exits are faster than entrances. A slow exit feels like lag; a slow
 *     entrance feels considered.
 *
 * Reduced motion is handled globally by <MotionConfig reducedMotion="user">
 * in ThemeProvider, so individual variants below don't need to branch.
 */

export const EASE_ORGANIC = [0.22, 1, 0.36, 1] as const;

export const DURATION = {
  micro: 0.15,
  standard: 0.25,
  enter: 0.3,
  exit: 0.2,
} as const;

export const transitions = {
  micro: { duration: DURATION.micro, ease: 'easeOut' },
  standard: { duration: DURATION.standard, ease: EASE_ORGANIC },
  /** Springs for anything the user directly manipulates — feels responsive. */
  press: { type: 'spring', stiffness: 400, damping: 28 },
  soft: { type: 'spring', stiffness: 220, damping: 30 },
} satisfies Record<string, Transition>;

/** Page-level route transition. Paired with AnimatePresence mode="wait". */
export const pageVariants: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: DURATION.enter, ease: EASE_ORGANIC } },
  exit: { opacity: 0, y: -8, transition: { duration: DURATION.exit, ease: 'easeIn' } },
};

/**
 * Stagger container. `staggerChildren` is capped deliberately: with 8+ children
 * a 0.06 stagger would run ~500ms and the last item reads as broken rather than
 * choreographed.
 */
export const staggerContainer: Variants = {
  initial: {},
  animate: {
    transition: { staggerChildren: 0.06, delayChildren: 0.04 },
  },
};

export const staggerItem: Variants = {
  initial: { opacity: 0, y: 16 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.standard, ease: EASE_ORGANIC },
  },
};

/** Scale-in for result cards and modals. No overshoot — this is data UI. */
export const scaleIn: Variants = {
  initial: { opacity: 0, scale: 0.97 },
  animate: {
    opacity: 1,
    scale: 1,
    transition: { duration: DURATION.standard, ease: EASE_ORGANIC },
  },
  exit: { opacity: 0, scale: 0.98, transition: { duration: DURATION.exit } },
};

export const fadeUp: Variants = {
  initial: { opacity: 0, y: 20 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.enter, ease: EASE_ORGANIC },
  },
};

/** Chat message entrance — slides from the sender's side. */
export const messageVariants = (side: 'user' | 'assistant'): Variants => ({
  initial: { opacity: 0, y: 8, x: side === 'user' ? 8 : -8 },
  animate: {
    opacity: 1,
    y: 0,
    x: 0,
    transition: { duration: DURATION.standard, ease: EASE_ORGANIC },
  },
});

/**
 * Viewport config for scroll reveals. `once` prevents re-animating on scroll-up,
 * which is distracting; the negative margin fires the reveal slightly before the
 * element is fully visible so it never appears to "pop" late.
 */
export const revealViewport = { once: true, margin: '-80px' } as const;
