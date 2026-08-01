import type { ElementType, ReactNode } from 'react';
import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { EASE_ORGANIC, DURATION, revealViewport } from '@/lib/motion';

/**
 * Entrance animation wrappers that degrade to plain, visible markup.
 *
 * Why this exists rather than using <motion.div variants={...}> directly:
 *
 * A reveal implemented as `initial={{opacity: 0}} animate={{opacity: 1}}` makes
 * content invisible *by default* and depends on JavaScript completing to reveal
 * it. If the animation is interrupted — a stalled rAF, a slow device, a
 * staggered child whose turn never arrives — the content stays at opacity 0
 * permanently. That was observed in practice: the landing page's h1, body copy
 * and CTAs all rendered into the DOM but remained invisible, with only the
 * first child of each stagger group ever reaching opacity 1.
 *
 * `MotionConfig reducedMotion="user"` does not solve it. That setting strips
 * transforms but keeps opacity animating, so users who asked for reduced motion
 * still got staggered fades AND still carried the invisible-by-default risk.
 *
 * Here, when the user prefers reduced motion the element renders with no motion
 * props and no opacity styling at all — it is simply visible. Content
 * visibility never depends on an animation finishing.
 */

const container: Variants = {
  initial: {},
  animate: { transition: { staggerChildren: 0.06, delayChildren: 0.04 } },
};

const item: Variants = {
  initial: { opacity: 0, y: 16 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.standard, ease: EASE_ORGANIC },
  },
};

interface RevealProps {
  children: ReactNode;
  className?: string;
  /** Render as a different element (ul, ol, dl, section…). */
  as?: ElementType;
  /** Stagger direct <RevealItem> children instead of animating as one block. */
  stagger?: boolean;
  /** Trigger on scroll into view rather than on mount. */
  inView?: boolean;
}

export function Reveal({ children, className, as, stagger, inView }: RevealProps) {
  const reduced = useReducedMotion();
  const Tag = (as ?? 'div') as ElementType;

  if (reduced) {
    return <Tag className={className}>{children}</Tag>;
  }

  const MotionTag = motion(Tag);
  const trigger = inView
    ? ({ whileInView: 'animate', viewport: revealViewport } as const)
    : ({ animate: 'animate' } as const);

  return (
    <MotionTag
      className={className}
      variants={stagger ? container : item}
      initial="initial"
      {...trigger}
    >
      {children}
    </MotionTag>
  );
}

export function RevealItem({
  children,
  className,
  as,
}: {
  children: ReactNode;
  className?: string;
  as?: ElementType;
}) {
  const reduced = useReducedMotion();
  const Tag = (as ?? 'div') as ElementType;

  if (reduced) {
    return <Tag className={className}>{children}</Tag>;
  }

  const MotionTag = motion(Tag);
  return (
    <MotionTag className={className} variants={item}>
      {children}
    </MotionTag>
  );
}
