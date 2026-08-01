import { useMediaQuery } from '@/hooks/useMediaQuery';
import {
  CANOPY_LEAF_D,
  CANOPY_LEAVES,
  CANOPY_MIDRIB_D,
  CANOPY_VIEW,
  CANOPY_VIEW_BOX,
} from './canopy';

/**
 * Leaves hanging from the top of the viewport, in place of the flat tonal band
 * that used to sit under the navbar.
 *
 * Entirely static — no motion values, no scroll listener. The band rasterises
 * once and is never touched again, which is why 132 leaves cost nothing next to
 * the growth scene animating below it.
 *
 * The leaf is declared once in <defs> and stamped with <use>. `color` and
 * `opacity` are inheritable, so each stamp can carry its own tone and depth
 * without duplicating the geometry 132 times in the DOM.
 */
export function CanopyBorder() {
  const compact = useMediaQuery('(max-width: 639px)');

  return (
    <div
      className="pointer-events-none fixed inset-x-0 top-16 -z-10 overflow-hidden"
      aria-hidden="true"
    >
      <svg
        viewBox={compact ? CANOPY_VIEW_BOX.compact : CANOPY_VIEW_BOX.wide}
        // Width-driven: the band's height follows the viewport width, so the
        // canopy stays in proportion instead of stretching.
        preserveAspectRatio="xMidYMin meet"
        className="h-auto w-full text-primary"
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
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.1" />
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

        {CANOPY_LEAVES.map((leaf, i) => (
          <use
            key={i}
            href="#tm-canopy-leaf"
            transform={leaf.transform}
            className={leaf.tone}
            opacity={leaf.opacity}
          />
        ))}
      </svg>
    </div>
  );
}
