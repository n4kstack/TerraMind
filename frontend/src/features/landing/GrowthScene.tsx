import {
  motion,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from 'framer-motion';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import {
  BLOSSOMS,
  BRANCHES,
  CANOPY_GLOW,
  LEAF_D,
  SEEDLING_HALO,
  SPROUT_LEAVES,
  SPROUT_STEM,
  TRUNK_DRAW,
  TRUNK_PATH,
  VIEW,
  VIEW_BOX,
  CENTER,
  type Blossom,
  type Branch,
  type Foliage,
} from './growth';

/**
 * The scroll-driven seedling.
 *
 * A single crop plant sits at the foot of the viewport on load. Scrolling grows
 * it: the stem extends, the seedling's cotyledons give way to a thickening
 * trunk, limbs fork outward in the order their joints appear, each leafs out
 * behind its own tip, and the last thing to arrive is fruit. It is the season
 * the product is about, told once, in the background.
 *
 * Three things keep it cheap:
 *  - all geometry is precomputed in ./growth — nothing bezier-shaped runs per
 *    frame;
 *  - growth is expressed as `pathLength`, `scale` and `opacity` only, which
 *    Framer writes straight to the element outside React's render cycle, so
 *    scrolling never triggers a re-render;
 *  - phones drop the secondary limbs, the canopy washes and half the blossoms,
 *    and take a centred crop of the drawing rather than a shrunken copy of it.
 */

/** Scroll position at which the tree is fully grown, as a fraction of the
 *  document. Short of 1 so maturity lands with the closing section rather than
 *  somewhere in the footer. */
const GROWTH_COMPLETE_AT = 0.82;

function Trunk({ progress }: { progress: MotionValue<number> }) {
  const draw = useTransform(progress, [...TRUNK_DRAW.input], [...TRUNK_DRAW.output], {
    clamp: true,
  });
  const width = useTransform(progress, [0.02, 0.8], [8, 25], { clamp: true });

  return (
    <motion.path
      d={TRUNK_PATH}
      fill="none"
      stroke="currentColor"
      strokeOpacity={0.52}
      strokeLinecap="round"
      style={{ pathLength: draw, strokeWidth: width }}
    />
  );
}

function Limb({ branch, progress }: { branch: Branch; progress: MotionValue<number> }) {
  const draw = useTransform(progress, [branch.from, branch.to], [0, 1], { clamp: true });
  // A new limb is a shoot; it keeps thickening after it has stopped extending,
  // which is why this window outlasts the draw.
  const width = useTransform(progress, [branch.from, branch.to + 0.14], [2, branch.width], {
    clamp: true,
  });

  return (
    <motion.path
      d={branch.d}
      fill="none"
      stroke="currentColor"
      strokeOpacity={branch.order === 0 ? 0.48 : 0.36}
      strokeLinecap="round"
      style={{ pathLength: draw, strokeWidth: width }}
    />
  );
}

function Cluster({ foliage, progress }: { foliage: Foliage; progress: MotionValue<number> }) {
  const scale = useTransform(progress, [foliage.from, foliage.to], [0.3, 1], { clamp: true });
  const opacity = useTransform(
    progress,
    [foliage.from, foliage.from + (foliage.to - foliage.from) * 0.55],
    [0, 1],
    { clamp: true },
  );

  return (
    <motion.g
      style={{
        scale,
        opacity,
        // fill-box resolves the percentage origin against this group's own
        // bounding box, so the cluster unfurls from the branch joint. Without
        // it the origin resolves against the root viewBox and every cluster
        // slides toward the middle of the drawing as it grows.
        transformBox: 'fill-box',
        transformOrigin: foliage.origin,
      }}
    >
      {foliage.leaves.map((leaf, i) => (
        <path
          key={i}
          d={LEAF_D}
          transform={leaf.transform}
          className={leaf.tone}
          fill="currentColor"
          fillOpacity={leaf.opacity}
        />
      ))}
    </motion.g>
  );
}

function Seedling({ progress }: { progress: MotionValue<number> }) {
  // Held at full strength through the opening stretch of scroll, then handed
  // over to the trunk thickening through the same space. The overlap is what
  // makes the hand-off read as one plant rather than two drawings swapped.
  // Hands over sooner than it looks like it should. The seedling only has a job
  // at rest, and its leaves are the most opaque thing in the scene (0.78, so it
  // reads as the subject on load). Held to 0.2 it was still ~90% visible at
  // scrollY 300 — where the modules intro scrolls right over it, measuring
  // 2.65:1. The trunk is ~20% drawn by the time this clears, which is tall
  // enough for the handoff to still read as one plant.
  const opacity = useTransform(progress, [0, 0.06, 0.24], [1, 1, 0], { clamp: true });
  const scale = useTransform(progress, [0, 0.24], [1, 1.28], { clamp: true });

  return (
    <>
      {/* Outside the scaling group on purpose: inside it, the halo would widen
          the group's fill-box and drag the bottom-centre growth origin with
          it. */}
      <motion.circle
        cx={SEEDLING_HALO.cx}
        cy={SEEDLING_HALO.cy}
        r={SEEDLING_HALO.r}
        fill="url(#tm-canopy-glow)"
        style={{ opacity }}
      />
      <motion.g style={{ opacity, scale, transformBox: 'fill-box', transformOrigin: '50% 100%' }}>
        <path
          d={SPROUT_STEM}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.62}
          strokeWidth={7}
          strokeLinecap="round"
        />
        {SPROUT_LEAVES.map((leaf, i) => (
          <path
            key={i}
            d={LEAF_D}
            transform={leaf.transform}
            className={leaf.tone}
            fill="currentColor"
            fillOpacity={leaf.opacity}
          />
        ))}
      </motion.g>
    </>
  );
}

function Glow({
  glow,
  progress,
}: {
  glow: (typeof CANOPY_GLOW)[number];
  progress: MotionValue<number>;
}) {
  const opacity = useTransform(progress, [glow.from, glow.from + 0.3], [0, 1], { clamp: true });
  const scale = useTransform(progress, [glow.from, glow.from + 0.36], [0.55, 1], { clamp: true });

  return (
    <motion.circle
      cx={glow.cx}
      cy={glow.cy}
      r={glow.r}
      fill="url(#tm-canopy-glow)"
      style={{ opacity, scale, transformBox: 'fill-box', transformOrigin: '50% 50%' }}
    />
  );
}

function RootShadow({ progress }: { progress: MotionValue<number> }) {
  const scale = useTransform(progress, [0, 1], [0.28, 1], { clamp: true });
  return (
    <motion.ellipse
      cx={CENTER}
      cy={VIEW.ground + 6}
      rx={340}
      ry={14}
      fill="url(#tm-root-shadow)"
      style={{ scale, transformBox: 'fill-box', transformOrigin: '50% 50%' }}
    />
  );
}

/** One fruit, on its own beat. Each carries a soft halo so it reads as opening
 *  into the canopy rather than being switched on. */
function Fruit({ blossom, progress }: { blossom: Blossom; progress: MotionValue<number> }) {
  const opacity = useTransform(progress, [blossom.from, blossom.to], [0, 1], { clamp: true });
  // Overshoots slightly past full size before settling — the difference between
  // a bud opening and a dot appearing.
  const scale = useTransform(
    progress,
    [blossom.from, blossom.to, blossom.to + 0.05],
    [0.2, 1.18, 1],
    { clamp: true },
  );

  return (
    <motion.g
      className="text-accent"
      style={{ opacity, scale, transformBox: 'fill-box', transformOrigin: '50% 50%' }}
    >
      <circle cx={blossom.cx} cy={blossom.cy} r={blossom.halo} fill="url(#tm-blossom)" />
      <circle
        cx={blossom.cx}
        cy={blossom.cy}
        r={blossom.r}
        fill="currentColor"
        fillOpacity={0.8}
      />
    </motion.g>
  );
}

export function GrowthScene() {
  const reduced = useReducedMotion();
  const compact = useMediaQuery('(max-width: 639px)');

  const { scrollYProgress } = useScroll();
  // The spring is what makes this growth rather than a scrubbed video: the tree
  // keeps easing for a beat after the wheel stops.
  const eased = useSpring(scrollYProgress, {
    stiffness: 48,
    damping: 20,
    mass: 0.4,
    restDelta: 0.0004,
  });
  const scrolled = useTransform(eased, [0, GROWTH_COMPLETE_AT], [0, 1], { clamp: true });

  // Under reduced motion the scene is a still life of the mature tree: every
  // transform below reads a constant, so nothing ever moves.
  const settled = useMotionValue(1);
  const progress = reduced ? settled : scrolled;

  /**
   * The legibility budget.
   *
   * Scene opacity and the scrim multiply, so what actually decides whether body
   * copy is readable over a leaf is one number — the total alpha the brightest
   * leaf ends up painted at:
   *
   *     leafFill (<= 0.58) x sceneOpacity x (1 - scrim)
   *
   * Measured against this palette, that product has to stay at or under 0.18
   * for muted body copy to clear WCAG AA in BOTH themes; light is the binding
   * case, because muted-foreground is a mid grey against a near-white surface
   * and any green tint closes the gap from the other side. At 0.64 x 0.58 x
   * (1 - 0.52) the figure is 0.178, which measures 4.7:1 light and 6.9:1 dark.
   *
   * The first pass shipped at 0.59 and measured 2.4:1. It looked wonderful and
   * could not be read.
   */
  const sceneOpacity = useTransform(progress, [0, 0.12, 0.5, 1], [1, 1, 0.7, 0.52]);

  const footScrim = useTransform(progress, [0, 0.05], [0, 1], { clamp: true });

  const branches = compact ? BRANCHES.filter((b) => b.order === 0) : BRANCHES;
  // The inner half open first, so on phones — where the outer canopy is cropped
  // away anyway — those are exactly the ones worth keeping.
  const blossoms = compact ? BLOSSOMS.slice(0, Math.ceil(BLOSSOMS.length / 2)) : BLOSSOMS;

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-0 top-16 -z-10 overflow-hidden"
      aria-hidden="true"
    >
      {/* Soil haze, anchored to the layer's bottom edge rather than to the
          drawing, so it stays put however the viewBox happens to be fitted. */}
      <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-primary/[0.07] via-primary/[0.02] to-transparent sm:h-40" />

      <motion.div style={{ opacity: sceneOpacity }} className="absolute inset-0">
        <svg
          viewBox={compact ? VIEW_BOX.compact : VIEW_BOX.wide}
          // Bottom-anchored and centred, so the plant is rooted at the foot of
          // the viewport at every size. `meet` fits by height on desktop and by
          // width on phones, so the canopy is never clipped.
          preserveAspectRatio="xMidYMax meet"
          className="size-full text-primary"
        >
          <defs>
            <radialGradient id="tm-canopy-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.26" />
              <stop offset="65%" stopColor="currentColor" stopOpacity="0.09" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </radialGradient>
            {/* className sets `color` on the gradient itself, so the stops'
                currentColor resolves to the accent rather than the tree. */}
            <radialGradient id="tm-blossom" className="text-accent" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.24" />
              <stop offset="55%" stopColor="currentColor" stopOpacity="0.09" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="tm-root-shadow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.16" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </radialGradient>
          </defs>

          {!compact &&
            CANOPY_GLOW.map((glow) => (
              <Glow key={`${glow.cx}-${glow.cy}`} glow={glow} progress={progress} />
            ))}

          <RootShadow progress={progress} />
          <Trunk progress={progress} />

          {branches.map((branch) => (
            <Limb key={branch.d} branch={branch} progress={progress} />
          ))}

          {/* Foliage is drawn after every limb so leaves always sit over wood. */}
          {branches.map((branch) => (
            <Cluster key={`${branch.d}-leaves`} foliage={branch.foliage} progress={progress} />
          ))}

          {blossoms.map((blossom) => (
            <Fruit key={`${blossom.cx}-${blossom.cy}`} blossom={blossom} progress={progress} />
          ))}

          <Seedling progress={progress} />
        </svg>
      </motion.div>

      {/*
          Legibility scrim. Constant, not faded in with growth — it was ramped
          from zero so the seedling would be crisp on load, but at zero there is
          nothing between the aurora and the hero copy, and the aurora's blobs,
          wash and a drifting mote stack to ~0.4 alpha right where that
          paragraph sits. Measured, that was the single worst pixel on the page
          in both themes. Its own gradient already eases off over the bottom
          band, so the seedling loses almost nothing by this being on. */}
      <div className="growth-scrim absolute inset-0" />

      {/* Foot scrim: off at rest so the seedling stays crisp, on as soon as
          copy starts scrolling over the trunk base. */}
      <motion.div
        style={{ opacity: footScrim }}
        className="growth-scrim-foot absolute inset-x-0 bottom-0 h-[32%]"
      />
    </div>
  );
}
