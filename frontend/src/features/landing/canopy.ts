/**
 * The foliage border hanging from the top of the landing page.
 *
 * Replaces the flat tonal band that sat under the navbar — the top of the
 * growth scene's scrim, which read as a hard horizontal edge — with leaves that
 * hang down and stop at no particular line.
 *
 * Like ./growth, every path and transform is computed once at module scope from
 * a seeded PRNG: the same canopy on every load, no work at render, and nothing
 * here animates, so the whole band rasterises once.
 */

/**
 * The foliage occupies only the top ~240 units; the rest is fall room. Leaf
 * coordinates are unchanged by the taller box — the SVG is width-driven, so a
 * taller viewBox extends downward without moving or rescaling anything.
 */
export const CANOPY_VIEW = { width: 1440, height: 620, foliage: 240 } as const;

/** Fall distance in user units. Expressed in viewBox space on purpose: the SVG
 *  scales with its container, so this is responsive for free rather than needing
 *  a breakpoint-specific pixel value. */
export const CANOPY_FALL = 430;

/** Phones get a centred crop rather than a shrunken copy, so leaves keep a
 *  readable size instead of collapsing into green confetti. */
export const CANOPY_VIEW_BOX = {
  wide: `0 0 1440 620`,
  compact: `430 0 580 620`,
} as const;

export interface CanopyLeaf {
  transform: string;
  tone: 'text-primary' | 'text-secondary';
  opacity: number;
}

/** mulberry32 — same generator as the growth scene, different seed. */
function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const r1 = (n: number) => Math.round(n * 10) / 10;

/**
 * A serrated leaf outline, tip pointing along +x from its stem at the origin.
 *
 * Built from a half-width profile rather than hand-authored control points:
 * `sin(pi*t)` gives a shape that closes to a point at the stem and the tip, the
 * exponent biases the widest part toward the base, and a sine riding on top cuts
 * the teeth. Straight segments between samples are deliberate — teeth should be
 * sharp, and smoothing them produces a bay leaf.
 */
function serratedLeaf(length: number, halfWidth: number, teeth: number): string {
  const STEPS = 46;
  const profile = (t: number) => {
    const body = Math.sin(Math.PI * t) ** 0.72;
    const taper = 1 - 0.28 * t;
    const serration = 1 + 0.13 * Math.sin(teeth * 2 * Math.PI * t);
    return halfWidth * body * taper * serration;
  };

  const upper: string[] = [];
  const lower: string[] = [];
  for (let i = 0; i <= STEPS; i += 1) {
    const t = i / STEPS;
    const x = r1(length * t);
    const y = r1(profile(t));
    upper.push(`${x} ${-y}`);
    lower.push(`${x} ${y}`);
  }
  lower.reverse();

  return `M${upper.join(' L')} L${lower.join(' L')} Z`;
}

export const CANOPY_LEAF_D = serratedLeaf(46, 14.5, 9);
export const CANOPY_MIDRIB_D = 'M3 0 L41 0';

/**
 * How far the foliage reaches down at a given x.
 *
 * Mostly noise — the brief was that it should not end on a line. A mild bias
 * toward the edges is layered under it so the middle stays a little clearer,
 * which is where the hero copy sits.
 */
function reachAt(x: number, random: () => number): number {
  const edge = Math.abs((x / CANOPY_VIEW.width) * 2 - 1) ** 1.4;
  const wave =
    Math.sin(x * 0.011) * 26 + Math.sin(x * 0.0043 + 1.7) * 34 + Math.sin(x * 0.021 + 0.6) * 14;
  return 56 + edge * 80 + wave + random() * 22;
}

const SPREAD_FROM = -60;
const SPREAD_TO = CANOPY_VIEW.width + 60;
const COUNT = 210;

/**
 * Places one leaf at `x`.
 *
 * Extracted so a replacement leaf drops into the same distribution as the
 * original 210. The sequence of random() calls is identical to the original
 * inline version — changing it would reshuffle every existing leaf, and the
 * arrangement is meant to stay exactly as it is.
 */
interface PlacedLeaf extends CanopyLeaf {
  /** Paint order key. Deliberately NOT the opacity: the leaves are sorted for
   *  overlap, and deriving that from opacity means any brightness change
   *  silently reshuffles which leaf sits over which. Frozen to the original
   *  expression so the arrangement survives re-tuning. */
  order: number;
}

function placeAt(x: number, random: () => number): PlacedLeaf {
  {
    const reach = reachAt(x, random);

    // Depth is biased toward the top so the band is dense where it meets the
    // navbar and thins out as it descends — that gradient IS the ragged edge.
    // Squared harder than looks necessary: the tail of this distribution is
    // what separates "canopy with a ragged edge" from "leaves falling off".
    const depth = reach * random() ** 2.3;
    const y = -14 + depth;
    const settle = depth / reach;

    // Leaves hang: 90deg points straight down. Deeper ones hang straighter,
    // the ones packed at the top splay sideways.
    const spread = (1 - settle) * 78 + 26;
    const angle = 90 + (random() - 0.5) * 2 * spread;

    const scale = (0.42 + random() * 0.46) * (1 - 0.2 * settle);

    const tone = random() > 0.45 ? 'text-secondary' : 'text-primary';
    const fade = random();

    return {
      transform: `translate(${r1(x)} ${r1(y)}) rotate(${r1(angle)}) scale(${r1(scale)})`,
      tone,
      // Deeper leaves fade, so the band dissolves instead of stopping.
      //
      // These were capped at 0.27 while the canopy was a fixed band that every
      // section scrolled behind — a leaf over the modules intro measured 4.42:1.
      // Now that the band is scoped to the hero, the only copy behind it is the
      // hero's own, which gets a local scrim, so the leaves can be vibrant.
      opacity: r1((0.42 + fade * 0.34) * (1 - 0.5 * settle ** 1.2)),
      // r1() is load-bearing, not cosmetic. The original key was the rounded
      // opacity, so leaves tied at one decimal and a stable sort left them in
      // build order. An unrounded key breaks those ties differently and
      // reshuffles the overlap.
      order: r1((0.14 + fade * 0.13) * (1 - 0.5 * settle ** 1.2)),
    };
  }
}

function build(): CanopyLeaf[] {
  const random = seeded(0x5ac31f);
  const leaves: PlacedLeaf[] = [];
  for (let i = 0; i < COUNT; i += 1) {
    // Even spread with jitter, rather than uniform random, which clumps.
    const x = SPREAD_FROM + ((SPREAD_TO - SPREAD_FROM) * (i + random() * 0.9)) / COUNT;
    leaves.push(placeAt(x, random));
  }
  // Painter's order, unchanged from the original arrangement.
  return leaves.sort((a, b) => b.order - a.order).map(({ order: _order, ...leaf }) => leaf);
}

export const CANOPY_LEAVES: readonly CanopyLeaf[] = build();

/**
 * A fresh leaf anywhere in the band, for replacing one that has fallen.
 *
 * Uses Math.random rather than the seeded stream on purpose — replacements
 * should differ between sessions, where the base arrangement should not.
 */
export function randomCanopyLeaf(): CanopyLeaf {
  const x = SPREAD_FROM + Math.random() * (SPREAD_TO - SPREAD_FROM);
  const { order: _order, ...leaf } = placeAt(x, Math.random);
  return leaf;
}
