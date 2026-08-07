/**
 * GENERATED FILE -- do not edit by hand.
 *
 * Written by frontend/scripts/extract-hero-frames.py from AI_Video_Prompt_–_Wheat_Crop_G.mp4.
 * Re-run that script to change the frame count, tier widths or source clip.
 */

export interface HeroTier {
  /** Public path prefix, without the frame number. */
  readonly dir: string;
  readonly width: number;
  readonly height: number;
}

/** Total stills per tier. Both tiers are the same length, so one index drives both. */
export const HERO_FRAME_COUNT = 120;

export const HERO_TIERS = {
  wide: { dir: '/hero/wide', width: 1280, height: 720 },
  compact: { dir: '/hero/compact', width: 720, height: 406 },
} as const satisfies Record<string, HeroTier>;

/** `/hero/wide/frame-0042.webp` */
export function heroFrameUrl(tier: HeroTier, index: number): string {
  return `${tier.dir}/frame-${String(index).padStart(4, '0')}.webp`;
}
