import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { useReducedMotion } from 'framer-motion';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import {
  CANOPY_FALL,
  CANOPY_LEAF_D,
  CANOPY_LEAVES,
  CANOPY_MIDRIB_D,
  CANOPY_VIEW,
  CANOPY_VIEW_BOX,
  randomCanopyLeaf,
  type CanopyLeaf,
} from './canopy';

/**
 * Leaves hanging over the hero, one of which falls every twenty seconds.
 *
 * Scoped to the hero rather than pinned under the navbar. That is what lets the
 * leaves be vibrant: as a fixed band, every section on the page scrolled behind
 * it, so leaf alpha was capped at a measured contrast ceiling. Anchored to the
 * hero, the only copy behind them is the hero's own — which gets a local scrim —
 * and the foliage is free to be as strong as it should be.
 *
 * The leaf geometry is declared once in <defs> and stamped with <use>: `color`
 * and `opacity` inherit, so 210 stamps carry their own tone and depth without
 * 210 copies of the path.
 */

const FALL_INTERVAL_MS = 20_000;

type LeafPhase = 'idle' | 'falling' | 'entering';

interface LiveLeaf extends CanopyLeaf {
  id: number;
  phase: LeafPhase;
}

export function CanopyBorder() {
  const compact = useMediaQuery('(max-width: 639px)');
  const reduced = useReducedMotion();

  const [leaves, setLeaves] = useState<LiveLeaf[]>(() =>
    CANOPY_LEAVES.map((leaf, i) => ({ ...leaf, id: i, phase: 'idle' })),
  );
  const nextId = useRef(CANOPY_LEAVES.length);

  useEffect(() => {
    if (reduced) return;

    const timer = window.setInterval(() => {
      setLeaves((prev) => {
        // Exactly one in flight at a time. A slow frame could otherwise let a
        // second interval fire while the first leaf is still on its way down.
        if (prev.some((leaf) => leaf.phase === 'falling')) return prev;

        const idle = prev.filter((leaf) => leaf.phase === 'idle');
        if (idle.length === 0) return prev;

        // Uniform over the whole set. The leaves are laid out evenly across the
        // width by construction, so a uniform pick is also uniform across the
        // band — no side is favoured.
        const chosen = idle[Math.floor(Math.random() * idle.length)]!;

        // The replacement appears as the original detaches, so the visible count
        // never dips and no hole is left where the leaf used to be.
        const replacement: LiveLeaf = {
          ...randomCanopyLeaf(),
          id: nextId.current,
          phase: 'entering',
        };
        nextId.current += 1;

        return [
          ...prev.map((leaf) =>
            leaf.id === chosen.id ? { ...leaf, phase: 'falling' as const } : leaf,
          ),
          replacement,
        ];
      });
    }, FALL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [reduced]);

  /** A fallen leaf leaves the set; a newcomer becomes an ordinary leaf, and so
   *  becomes eligible to fall itself later. */
  function onPhaseEnd(id: number, phase: LeafPhase) {
    setLeaves((prev) =>
      phase === 'falling'
        ? prev.filter((leaf) => leaf.id !== id)
        : prev.map((leaf) => (leaf.id === id ? { ...leaf, phase: 'idle' as const } : leaf)),
    );
  }

  return (
    <div
      className="pointer-events-none absolute inset-x-0 top-0 -z-10 overflow-hidden"
      aria-hidden="true"
    >
      <svg
        viewBox={compact ? CANOPY_VIEW_BOX.compact : CANOPY_VIEW_BOX.wide}
        // Width-driven, so the band and the fall scale with the viewport.
        preserveAspectRatio="xMidYMin meet"
        className="h-auto w-full text-primary"
        style={{ '--tm-fall': `${CANOPY_FALL}px` } as CSSProperties}
      >
        <defs>
          <g id="tm-canopy-leaf">
            <path d={CANOPY_LEAF_D} fill="currentColor" />
            <path
              d={CANOPY_MIDRIB_D}
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.4}
              strokeWidth={1.4}
              strokeLinecap="round"
            />
          </g>
          {/* Depth behind the leaf mass: without it the top edge reads as a row
              of cut-outs rather than foliage continuing past the frame. */}
          <linearGradient id="tm-canopy-depth" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.16" />
            <stop offset="55%" stopColor="currentColor" stopOpacity="0.05" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>

        <rect
          x={-80}
          y={-40}
          width={CANOPY_VIEW.width + 160}
          height={132}
          fill="url(#tm-canopy-depth)"
        />

        {leaves.map((leaf) => (
          <g
            key={leaf.id}
            // The class is attached only while animating: `transform-box:
            // fill-box` forces a bounding-box measurement, and there is no
            // reason to pay for that on 210 resting leaves.
            className={
              leaf.phase === 'falling'
                ? 'tm-leaf tm-leaf--falling'
                : leaf.phase === 'entering'
                  ? 'tm-leaf tm-leaf--enter'
                  : undefined
            }
            onAnimationEnd={
              leaf.phase === 'idle' ? undefined : () => onPhaseEnd(leaf.id, leaf.phase)
            }
          >
            <use
              href="#tm-canopy-leaf"
              transform={leaf.transform}
              className={leaf.tone}
              opacity={leaf.opacity}
            />
          </g>
        ))}
      </svg>
    </div>
  );
}
