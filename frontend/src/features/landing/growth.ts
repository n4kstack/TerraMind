/**
 * Geometry and choreography for the landing page's growth scene.
 *
 * Everything here — every path string, leaf transform and timing window — is
 * computed once at module scope. The component that renders it only maps scroll
 * progress onto motion values, so no bezier maths ever runs inside an animation
 * frame. That is the difference between this being free and this being the
 * reason the page drops frames on a mid-range Android.
 *
 * The irregularity that stops the tree looking machine-drawn comes from a
 * seeded PRNG rather than Math.random: the same tree on every load, and no
 * mismatch if this is ever rendered ahead of time.
 *
 * Coordinates live in a 1200x640 viewBox with the soil line at y=600. The tree
 * grows upward from (600, 600).
 */

/**
 * The drawing is authored far wider than it is tall so the mature canopy
 * spreads across the whole viewport instead of towering in a column. At this
 * aspect the SVG fits a desktop layer almost exactly edge to edge.
 */
export const VIEW = { width: 1200, height: 640, ground: 600 } as const;

/** Phones get a centred crop of the same drawing rather than a shrunken copy
 *  of it: a 1200-unit canopy scaled to 390px would be a smudge. The tree runs
 *  off both edges there, which is what a vast tree should do on a small
 *  screen. */
export const VIEW_BOX = {
  wide: `0 0 ${1200} ${640}`,
  compact: `300 0 600 640`,
} as const;

/** x of the trunk. */
export const CENTER = 600;

/** A single leaf, tip pointing along +x, ~29 units long before scaling. */
export const LEAF_D = 'M0 0 C 7 -8 20 -10 29 0 C 20 10 7 8 0 0 Z';

/** Tailwind colour classes; the shapes paint with `fill="currentColor"`. */
type Tone = 'text-primary' | 'text-secondary';

export interface Leaf {
  transform: string;
  tone: Tone;
  opacity: number;
}

export interface Foliage {
  leaves: Leaf[];
  /** transform-origin (percentage pair) placing the growth origin at the
   *  branch joint, so a cluster unfurls outward instead of ballooning. */
  origin: string;
  from: number;
  to: number;
}

export interface Branch {
  d: string;
  /** Stroke width once mature. Animated up from a sapling-thin start. */
  width: number;
  from: number;
  to: number;
  /** 0 = grows off the trunk, 1 = grows off another branch. */
  order: 0 | 1;
  foliage: Foliage;
  tip: Point;
  /** Kept so blossoms can be seated along the limb. */
  curve: Cubic;
}

interface Point {
  x: number;
  y: number;
}

/** Re-reads a point off a limb after the fact. Branches keep their curve so
 *  blossoms can be seated anywhere along them, not only at the tip. */
function pointOnPath(branch: Branch, t: number): Point {
  return bezierAt(branch.curve, t);
}

type Cubic = readonly [Point, Point, Point, Point];

const pt = (x: number, y: number): Point => ({ x, y });
const r1 = (n: number) => Math.round(n * 10) / 10;

/* ------------------------------------------------------------------ curves */

function bezierAt([p0, p1, p2, p3]: Cubic, t: number): Point {
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const c = 3 * u * t * t;
  const d = t * t * t;
  return pt(
    a * p0.x + b * p1.x + c * p2.x + d * p3.x,
    a * p0.y + b * p1.y + c * p2.y + d * p3.y,
  );
}

/** Heading of the curve at `t`, in degrees — leaves are rotated relative to it
 *  so they always sit along the limb rather than at arbitrary angles. */
function bezierAngle([p0, p1, p2, p3]: Cubic, t: number): number {
  const u = 1 - t;
  const dx = 3 * u * u * (p1.x - p0.x) + 6 * u * t * (p2.x - p1.x) + 3 * t * t * (p3.x - p2.x);
  const dy = 3 * u * u * (p1.y - p0.y) + 6 * u * t * (p2.y - p1.y) + 3 * t * t * (p3.y - p2.y);
  return (Math.atan2(dy, dx) * 180) / Math.PI;
}

function cubicPath(c: Cubic): string {
  return `M${r1(c[0].x)} ${r1(c[0].y)} C ${r1(c[1].x)} ${r1(c[1].y)} ${r1(c[2].x)} ${r1(c[2].y)} ${r1(c[3].x)} ${r1(c[3].y)}`;
}

function splinePath(segments: readonly [Cubic, ...Cubic[]]): string {
  const start = segments[0][0];
  let d = `M${r1(start.x)} ${r1(start.y)}`;
  for (const [, p1, p2, p3] of segments) {
    d += ` C ${r1(p1.x)} ${r1(p1.y)} ${r1(p2.x)} ${r1(p2.y)} ${r1(p3.x)} ${r1(p3.y)}`;
  }
  return d;
}

/** Parametrised uniformly per segment. The trunk's three segments are near
 *  enough equal length that the arc-length error is invisible, and this avoids
 *  sampling the path through the DOM. */
function splineAt(segments: readonly [Cubic, ...Cubic[]], t: number): Point {
  const clamped = Math.min(Math.max(t, 0), 1);
  const scaled = clamped * segments.length;
  const index = Math.min(Math.floor(scaled), segments.length - 1);
  return bezierAt(segments[index] ?? segments[0], scaled - index);
}

/** mulberry32 — small, fast, and deterministic from a fixed seed. */
function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ------------------------------------------------------------------- trunk */

const TRUNK_SPLINE: readonly [Cubic, ...Cubic[]] = [
  [pt(600, 600), pt(588, 528), pt(614, 484), pt(600, 428)],
  [pt(600, 428), pt(586, 376), pt(616, 336), pt(597, 284)],
  [pt(597, 284), pt(583, 242), pt(610, 214), pt(600, 170)],
];

export const TRUNK_PATH = splinePath(TRUNK_SPLINE);

/**
 * How far the trunk has extended, against scroll. Deliberately slow out of the
 * gate: drawn linearly the trunk outruns its own foliage and the plant spends
 * the first third of the page as a bare pole waiting for leaves.
 */
export const TRUNK_DRAW = {
  input: [0, 0.14, 0.38, 0.68],
  output: [0.05, 0.13, 0.46, 1],
} as const;

/** Scroll position at which the trunk has extended past `fraction` — the
 *  inverse of the curve above. Limbs are scheduled from this rather than from
 *  hand-picked numbers, so a limb can never start growing off a stretch of
 *  trunk that does not exist yet. */
function trunkReaches(fraction: number): number {
  const { input, output } = TRUNK_DRAW;
  for (let i = 1; i < output.length; i += 1) {
    const lo = output[i - 1] as number;
    const hi = output[i] as number;
    if (fraction <= hi) {
      const atLo = input[i - 1] as number;
      const atHi = input[i] as number;
      return atLo + ((fraction - lo) / (hi - lo)) * (atHi - atLo);
    }
  }
  return input[input.length - 1] as number;
}

/* ------------------------------------------------------------------ sprout */

/**
 * The seedling shown before the trunk takes over: a stem, one pair of
 * cotyledons and a pair of true leaves. It cross-fades out as the trunk
 * thickens through the same space, which is what makes the hand-off read as
 * one continuous plant rather than two drawings swapped.
 */
export const SPROUT_STEM = 'M600 600 C 594 568 606 538 600 494';

export const SPROUT_LEAVES: Leaf[] = [
  { transform: 'translate(590 556) rotate(197) scale(2.1)', tone: 'text-secondary', opacity: 0.78 },
  { transform: 'translate(610 562) rotate(-21) scale(2.1)', tone: 'text-secondary', opacity: 0.78 },
  { transform: 'translate(594 514) rotate(213) scale(1.55)', tone: 'text-primary', opacity: 0.7 },
  { transform: 'translate(606 518) rotate(-39) scale(1.55)', tone: 'text-primary', opacity: 0.7 },
  { transform: 'translate(600 494) rotate(-84) scale(1.15)', tone: 'text-secondary', opacity: 0.66 },
];

/** Soft light pooled around the seedling on load. It is the only thing on the
 *  page at that moment, and without it a 90px sprout at the foot of a 1440px
 *  hero reads as an accident rather than the subject. Fades out as the plant
 *  outgrows it. */
export const SEEDLING_HALO = { cx: CENTER, cy: 534, r: 168 } as const;

/* ------------------------------------------------------------------ canopy */

/**
 * Timing. Growth is expressed in normalised scroll progress (0 = top of the
 * page, 1 = growth complete). A limb starts drawing only once the trunk has
 * reached its joint, which is what makes the sequence feel grown rather than
 * assembled.
 */
const LIMB_SPAN = 0.11;

interface LimbSpec {
  /** Position along the trunk, 0 at the soil, 1 at the crown. */
  t: number;
  dir: -1 | 1;
  len: number;
  rise: number;
  /** Whether a secondary limb forks off this one. */
  fork: boolean;
}

const LIMBS: readonly LimbSpec[] = [
  { t: 0.2, dir: -1, len: 440, rise: 195, fork: true },
  { t: 0.28, dir: 1, len: 470, rise: 210, fork: true },
  { t: 0.4, dir: -1, len: 395, rise: 205, fork: true },
  { t: 0.5, dir: 1, len: 360, rise: 200, fork: true },
  { t: 0.62, dir: -1, len: 290, rise: 175, fork: true },
  { t: 0.72, dir: 1, len: 250, rise: 160, fork: true },
  { t: 0.84, dir: -1, len: 175, rise: 135, fork: false },
  { t: 0.93, dir: 1, len: 125, rise: 105, fork: false },
  { t: 1.0, dir: -1, len: 45, rise: 85, fork: false },
];

/**
 * Leaves the trunk near-level, dips under its own weight, then sweeps up to the
 * tip. `sag` is how far it droops before it lifts, and it is most of what
 * separates "tree" from "star" — with the control points pulled straight, a
 * 440-unit limb reads as a spoke however good the foliage on it is.
 */
function limb(origin: Point, dir: -1 | 1, len: number, rise: number, sag = 0.12): Cubic {
  return [
    origin,
    pt(origin.x + dir * len * 0.3, origin.y + rise * sag),
    pt(origin.x + dir * len * 0.72, origin.y - rise * 0.42),
    pt(origin.x + dir * len, origin.y - rise),
  ];
}

function foliageFor(
  curve: Cubic,
  count: number,
  from: number,
  to: number,
  random: () => number,
): Foliage {
  const leaves: Leaf[] = [];
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (let i = 0; i < count; i += 1) {
    // Nothing before 0.4: bare limb near the trunk, foliage toward the tip.
    const t = 0.4 + (0.6 * i) / (count - 1);
    const base = bezierAt(curve, t);
    const heading = bezierAngle(curve, t);
    const side = i % 2 === 0 ? -1 : 1;
    const scale = 1.25 + random() * 0.5;

    leaves.push({
      transform: `translate(${r1(base.x)} ${r1(base.y)}) rotate(${r1(heading + side * (30 + random() * 26))}) scale(${r1(scale)})`,
      tone: random() > 0.42 ? 'text-secondary' : 'text-primary',
      // Capped deliberately. Scene opacity and the legibility scrim multiply
      // with this, and the product is what governs whether body copy laid over
      // a leaf clears WCAG AA — see the budget in GrowthScene.
      opacity: r1(0.38 + random() * 0.2),
    });

    // Conservative footprint: a leaf never reaches further than its own length
    // from its stem, whatever the rotation.
    const reach = 32 * scale;
    minX = Math.min(minX, base.x - reach);
    maxX = Math.max(maxX, base.x + reach);
    minY = Math.min(minY, base.y - reach);
    maxY = Math.max(maxY, base.y + reach);
  }

  const joint = curve[0];
  return {
    leaves,
    origin: `${r1(((joint.x - minX) / (maxX - minX)) * 100)}% ${r1(((joint.y - minY) / (maxY - minY)) * 100)}%`,
    from,
    to,
  };
}

function build(): Branch[] {
  const random = seeded(0x7e44a1);
  const branches: Branch[] = [];

  for (const spec of LIMBS) {
    const curve = limb(splineAt(TRUNK_SPLINE, spec.t), spec.dir, spec.len, spec.rise);
    const from = trunkReaches(spec.t);
    const to = from + LIMB_SPAN;

    branches.push({
      d: cubicPath(curve),
      width: r1(6 + (1 - spec.t) * 8),
      from,
      to,
      order: 0,
      foliage: foliageFor(curve, 7, to - 0.05, to + 0.09, random),
      tip: bezierAt(curve, 1),
      curve,
    });

    if (!spec.fork) continue;

    const fork = limb(
      bezierAt(curve, 0.56),
      spec.dir,
      spec.len * 0.42,
      spec.rise * 0.66,
      0.1,
    );
    const forkFrom = to - 0.02;
    const forkTo = forkFrom + 0.1;

    branches.push({
      d: cubicPath(fork),
      width: r1(3.4 + (1 - spec.t) * 3.4),
      from: forkFrom,
      to: forkTo,
      order: 1,
      foliage: foliageFor(fork, 5, forkTo - 0.04, forkTo + 0.09, random),
      tip: bezierAt(fork, 1),
      curve: fork,
    });
  }

  return branches;
}

export const BRANCHES: readonly Branch[] = build();

export interface Blossom {
  cx: number;
  cy: number;
  r: number;
  halo: number;
  from: number;
  to: number;
}

/**
 * Fruit, scattered through the canopy rather than pinned to the limb tips, and
 * opening one at a time.
 *
 * The order is inner-canopy-outward, so blossoming spreads through the tree the
 * way it spread through the branches — a single group fade would land as one
 * event and lose the whole point. This is also the only place the accent colour
 * appears in the scene, which is what makes it read as an arrival.
 */
function blossoms(): Blossom[] {
  const random = seeded(0x2f19c7);
  const seats = BRANCHES.filter((b) => b.order === 0).flatMap((b) =>
    // Two per limb: one out at the tip, one back along the branch.
    [0.62, 0.93].map((t) => {
      const at = pointOnPath(b, t);
      return {
        cx: r1(at.x + (random() - 0.5) * 26),
        cy: r1(at.y + 14 + random() * 18),
        r: r1(6.5 + random() * 3.5),
        span: Math.abs(at.x - CENTER),
      };
    }),
  );

  // Inner blossoms open first.
  seats.sort((a, b) => a.span - b.span);

  const OPEN_FROM = 0.7;
  const OPEN_WINDOW = 0.24;
  const OPEN_SPAN = 0.07;
  const step = OPEN_WINDOW / Math.max(seats.length - 1, 1);

  return seats.map((seat, i) => ({
    cx: seat.cx,
    cy: seat.cy,
    r: seat.r,
    halo: r1(seat.r * 3.2),
    // Deliberately NOT rounded. r1() is for coordinates; rounding a schedule to
    // one decimal collapsed `from` and `to` onto the same value for a third of
    // these, and a zero-width useTransform range evaluates to NaN. The style
    // system drops a NaN opacity rather than throwing, so those blossoms sat
    // fully open at the top of the page.
    from: OPEN_FROM + i * step,
    to: OPEN_FROM + i * step + OPEN_SPAN,
  }));
}

export const BLOSSOMS: readonly Blossom[] = blossoms();

/**
 * Soft volume behind the canopy. Three overlapping radial washes read as depth
 * far more cheaply than an SVG blur filter, which would re-rasterise on every
 * frame of the scroll.
 */
export const CANOPY_GLOW = [
  { cx: 600, cy: 350, r: 380, from: 0.5 },
  { cx: 320, cy: 400, r: 260, from: 0.42 },
  { cx: 890, cy: 310, r: 280, from: 0.58 },
] as const;
