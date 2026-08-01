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

export const CANOPY_VIEW = { width: 1440, height: 240 } as const;

/** Phones get a centred crop rather than a shrunken copy, so leaves keep a
 *  readable size instead of collapsing into green confetti. */
export const CANOPY_VIEW_BOX = {
  wide: `0 0 1440 240`,
  compact: `430 0 580 240`,
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

function build(): CanopyLeaf[] {
  const random = seeded(0x5ac31f);
  const leaves: CanopyLeaf[] = [];

  // Overhang both edges so the band never shows a seam at the viewport border.
  const from = -60;
  const to = CANOPY_VIEW.width + 60;
  const COUNT = 210;

  for (let i = 0; i < COUNT; i += 1) {
    // Even spread with jitter, rather than uniform random, which clumps.
    const x = from + ((to - from) * (i + random() * 0.9)) / COUNT;
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

    leaves.push({
      transform: `translate(${r1(x)} ${r1(y)}) rotate(${r1(angle)}) scale(${r1(scale)})`,
      tone: random() > 0.45 ? 'text-secondary' : 'text-primary',
      // Deeper leaves fade, so the band dissolves instead of stopping.
      //
      // The ceiling is measured, not chosen. This layer paints ABOVE the growth
      // scene's legibility scrim, so nothing dims it, and page content scrolls
      // straight through the band underneath. At 0.35 a leaf behind the modules
      // intro measured 4.42:1 in dark mode. Dark is the binding case: light-mode
      // body copy on this page is --foreground and clears comfortably, but dark
      // keeps the muted tone and sits far closer to a mid-green leaf.
      opacity: r1((0.14 + random() * 0.13) * (1 - 0.5 * settle ** 1.2)),
    });
  }

  // Painter's order: deepest first, so the dense top mass overlaps the stragglers.
  return leaves.sort((a, b) => b.opacity - a.opacity);
}

export const CANOPY_LEAVES: readonly CanopyLeaf[] = build();
