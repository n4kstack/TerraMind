import { useCallback, useEffect, useRef } from 'react';
import type { MotionValue } from 'framer-motion';
import { useFrameSequence } from './useFrameSequence';
import { HERO_TIERS, type HeroTier } from './frameManifest';

/**
 * Draws the hero sequence, one still per scroll position.
 *
 * This is the whole trick: scroll offset picks an index, the index picks an
 * image, and the image is painted `cover` into a full-bleed canvas. There is no
 * <video> element and nothing plays on its own — stop scrolling and the footage
 * stops on that frame, scroll up and it runs backwards. A <video> cannot do
 * this. Seeking one per scroll tick stutters on every browser (seeks resolve to
 * keyframes, and `currentTime` writes settle asynchronously), which is exactly
 * why the sequence is pre-split into stills.
 *
 * Nothing here re-renders React. `progress` is a MotionValue, so scrolling
 * writes to a canvas through a rAF and never touches the component tree.
 */

/** Above 2x the extra fill rate buys nothing visible on footage and costs real
 *  frames on phones that report 3x. */
const MAX_DPR = 2;

interface ScrollFrameCanvasProps {
  /** 0..1 across the pinned section. */
  progress: MotionValue<number>;
  /** Narrow viewports take the light tier and load half as many stills. */
  compact: boolean;
  /** Surfaced so the hero can hold its scroll cue back while the first still is in flight. */
  onReadyChange?: (ready: boolean) => void;
}

export function ScrollFrameCanvas({ progress, compact, onReadyChange }: ScrollFrameCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const tier: HeroTier = compact ? HERO_TIERS.compact : HERO_TIERS.wide;

  const { ready, progress: loaded, blendAt, count } = useFrameSequence(tier, compact ? 2 : 1, true);

  // Read the loader through a ref inside the draw path. Closing over `blendAt`
  // directly would pin the rAF loop to the first render's copy, and putting it
  // in the effect's deps would tear the loop down and rebuild it on every
  // still that lands — mid-scroll, dozens of times.
  const blendAtRef = useRef(blendAt);
  blendAtRef.current = blendAt;

  const paint = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !canvas.width) return;

    // Fractional, not rounded. The fraction is the whole point: rounding to the
    // nearest still is what made this step rather than move.
    const { from, to, t } = blendAtRef.current(progress.get() * (count - 1));
    if (!from?.naturalWidth) return;

    // `alpha: false` lets the compositor skip blending the canvas against what
    // is behind it. The footage is opaque and covers the element completely.
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    const { width, height } = canvas;
    // `cover`: fill both axes and let the overflow crop, rather than
    // letterboxing a 16:9 clip into a tall phone viewport.
    const cover = (image: HTMLImageElement) => {
      const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
      const drawWidth = image.naturalWidth * scale;
      const drawHeight = image.naturalHeight * scale;
      ctx.drawImage(
        image,
        (width - drawWidth) / 2,
        (height - drawHeight) / 2,
        drawWidth,
        drawHeight,
      );
    };

    ctx.globalAlpha = 1;
    cover(from);

    // Dissolve the next still in over the top, weighted by how far between the
    // two the scroll actually sits. This is what turns 12 stills per second of
    // footage into continuous motion — the eye reads the blend as a frame that
    // was never shot, so the sequence stops looking like a flipbook without a
    // single extra byte on the wire.
    if (to?.naturalWidth && t > 0.001) {
      ctx.globalAlpha = t;
      cover(to);
      ctx.globalAlpha = 1;
    }
  }, [progress, count]);

  useEffect(() => {
    onReadyChange?.(ready);
  }, [ready, onReadyChange]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let raf = 0;
    let queued = false;

    // Coalesce to one paint per animation frame. A trackpad emits scroll events
    // faster than the display refreshes, and painting per event would redraw
    // the same pixels several times between two frames anyone can see.
    const schedule = () => {
      if (queued) return;
      queued = true;
      raf = requestAnimationFrame(() => {
        queued = false;
        paint();
      });
    };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      const rect = canvas.getBoundingClientRect();
      const width = Math.round(rect.width * dpr);
      const height = Math.round(rect.height * dpr);
      // Assigning width/height clears the canvas, so this has to be guarded.
      // Mobile browsers fire a resize whenever the URL bar slides, and an
      // unconditional write would blank the hero on every scroll direction
      // change.
      if (canvas.width === width && canvas.height === height) return;
      canvas.width = width;
      canvas.height = height;
      paint();
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    const unsubscribe = progress.on('change', schedule);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      unsubscribe();
    };
  }, [progress, paint]);

  // Repaint as stills land. The loader routinely fills in the frame under the
  // user's current scroll position without `progress` having changed, and
  // without this the canvas would sit on the older, further-back frame until
  // the next scroll event.
  useEffect(() => {
    const raf = requestAnimationFrame(paint);
    return () => cancelAnimationFrame(raf);
  }, [loaded, paint]);

  return (
    <canvas
      ref={canvasRef}
      // Decorative. The hero's meaning is carried by the copy layered over it,
      // which is real text; announcing the footage here would add nothing a
      // screen reader user can act on.
      aria-hidden="true"
      className="size-full"
      // Held at 0 until the first still settles, so the hero fades up from the
      // stage colour instead of flashing an empty canvas on a cold load. Note
      // this element never gets a 2d context until there is something to draw:
      // the context is requested with `alpha: false`, so creating it eagerly
      // would paint an opaque black rectangle over the stage for as long as the
      // sequence was missing or in flight.
      style={{
        opacity: ready ? 1 : 0,
        transition: 'opacity 500ms cubic-bezier(0.22, 1, 0.36, 1)',
      }}
    />
  );
}
