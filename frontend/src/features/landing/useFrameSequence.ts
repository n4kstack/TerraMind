import { useEffect, useRef, useState } from 'react';
import { HERO_FRAME_COUNT, heroFrameUrl, type HeroTier } from './frameManifest';

/**
 * Progressive loader for the scroll-scrubbed hero stills.
 *
 * The sequence is the heaviest thing on the site, so the one rule here is that
 * nothing waits for all of it. Frame 0 is fetched on its own and paints the
 * moment it lands; the rest stream in behind it, in scroll order, and the
 * scrubber draws the nearest frame it already has. Scrolling ahead of the
 * download shows a slightly stale still rather than a blank canvas — a dropped
 * frame, not a broken hero.
 *
 * Three deliberate choices:
 *
 *  - HTMLImageElement, not createImageBitmap. An ImageBitmap is a decoded
 *    surface: 120 of them at 1440x810 is ~560 MB of RSS, which is an instant
 *    kill on a mid-range Android. The browser holds <img> compressed and
 *    manages decode eviction itself under memory pressure.
 *
 *  - `decode()` is awaited before a frame counts as loaded. Without it the
 *    first drawImage of each still decodes synchronously on the main thread,
 *    which is a 10-20ms jank spike landing exactly during a scroll gesture.
 *
 *  - A fixed-size pool rather than firing every request at once. 120 parallel
 *    fetches starve the chunk and font requests the page still needs, and on a
 *    slow connection they all arrive late together instead of in order.
 */

/** Concurrent in-flight requests. Enough to saturate a connection, few enough
 *  to leave room for the rest of the page's critical path. */
const POOL_SIZE = 6;

export interface FrameSequence {
  /** Total addressable frames. Index space is always 0..count-1, whatever the stride. */
  count: number;
  /**
   * True once the first frame has *settled* — decoded, or definitively failed.
   *
   * Settled, not loaded, and the distinction is deliberate: this gates how long
   * the stage sits waiting, and a sequence that 404s should stop the wait
   * rather than extend it forever. With no frames on disk the hero falls back
   * to a bare --hero-void stage with the copy on it, which is a presentable
   * dark hero; leaving it permanently mid-load instead would suppress the
   * scroll cue on a page that scrolls perfectly well without the footage.
   */
  ready: boolean;
  /** 0..1, how much of the sequence is resident. Drives the loading meter. */
  progress: number;
  /** Nearest loaded frame at or before `index`, or null before the first arrives. */
  frameAt: (index: number) => HTMLImageElement | null;
  /**
   * The two loaded stills bracketing a fractional position, and how far between
   * them it sits. Lets the canvas cross-dissolve rather than snap: 120 stills
   * over ten seconds is 12fps, and stepping between them is plainly visible.
   */
  blendAt: (position: number) => FrameBlend;
}

export interface FrameBlend {
  /** The still at or before `position`. Null only before anything has loaded. */
  from: HTMLImageElement | null;
  /** The next loaded still, or null at the end of the sequence. */
  to: HTMLImageElement | null;
  /** 0..1 across the gap between them. */
  t: number;
}

/**
 * @param tier   Which encoded set to pull. Chosen by viewport, not by network.
 * @param stride Load every Nth frame. The phone tier halves its resident set
 *               this way; the sequence still spans the same scroll distance,
 *               it just advances in twos. Cheaper than re-encoding a second
 *               shorter set, and tunable without touching the frames on disk.
 * @param enabled Skip all fetching (reduced motion renders a single still).
 */
export function useFrameSequence(
  tier: HeroTier,
  stride: number,
  enabled: boolean,
): FrameSequence {
  const framesRef = useRef<Map<number, HTMLImageElement>>(new Map());
  const [ready, setReady] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!enabled) return;

    const frames = framesRef.current;
    frames.clear();
    setReady(false);
    setProgress(0);

    let cancelled = false;

    // Index 0 is always first: `load(0)` below is hoisted out of the pool, and
    // the pool starts from index 1 of this list.
    const wanted: number[] = [];
    for (let i = 0; i < HERO_FRAME_COUNT; i += stride) wanted.push(i);
    // The final frame is what the hero rests on when the pin releases. Unless
    // the stride happens to divide the sequence evenly it would never be
    // fetched, and the footage would visibly stop short of its own ending.
    const last = HERO_FRAME_COUNT - 1;
    if (wanted[wanted.length - 1] !== last) wanted.push(last);

    const load = (index: number) =>
      new Promise<void>((resolve) => {
        const img = new Image();
        img.decoding = 'async';
        img.src = heroFrameUrl(tier, index);

        const settle = () => {
          if (!cancelled) {
            frames.set(index, img);
            setProgress(frames.size / wanted.length);
          }
          resolve();
        };

        img
          .decode()
          .then(settle)
          // decode() rejects on a 404 and, in some browsers, on a still-empty
          // src. Falling back to the load event keeps one missing frame from
          // stalling the pool; a frame that never arrives is simply skipped by
          // frameAt().
          .catch(() => {
            img.onload = settle;
            img.onerror = () => resolve();
          });
      });

    // Frame 0 alone, ahead of the pool: it is the only frame that blocks the
    // hero from painting, so it must not queue behind five of its successors.
    // Resolves on failure as well as success — see `ready` above.
    void load(0).then(() => {
      if (!cancelled) setReady(true);
    });

    let next = 1;
    const pump = async (): Promise<void> => {
      while (!cancelled) {
        const index = wanted[next++];
        if (index === undefined) return;
        await load(index);
      }
    };
    const pool = Array.from({ length: POOL_SIZE }, pump);
    void Promise.all(pool);

    return () => {
      cancelled = true;
      // Drop references so the decoded surfaces become collectable on unmount;
      // without this, navigating away from the landing page keeps the whole
      // sequence resident for the life of the tab.
      frames.clear();
    };
  }, [tier, stride, enabled]);

  const frameAt = (index: number): HTMLImageElement | null => {
    const frames = framesRef.current;
    const clamped = Math.min(HERO_FRAME_COUNT - 1, Math.max(0, index));

    // Walk backwards to the nearest resident frame. Backwards rather than to
    // the nearest in either direction: holding the last frame the user actually
    // saw reads as the footage pausing, while jumping forward to a frame the
    // in-between of which never loaded reads as a skip.
    for (let i = clamped; i >= 0; i--) {
      const hit = frames.get(i);
      if (hit) return hit;
    }
    // Nothing behind it yet — scrolled past the download on a cold cache. Any
    // frame beats an empty canvas.
    for (let i = clamped + 1; i < HERO_FRAME_COUNT; i++) {
      const hit = frames.get(i);
      if (hit) return hit;
    }
    return null;
  };

  /**
   * Walk out from `index` to the nearest still that is actually resident.
   *
   * `step` of -1 searches backwards, +1 forwards. Loaded indices sit on a
   * lattice of `stride`, so this normally terminates on the first or second
   * probe; the loop exists for the cold-cache case where the pool has not
   * reached this part of the sequence yet.
   */
  const seek = (index: number, step: -1 | 1): [HTMLImageElement, number] | null => {
    const frames = framesRef.current;
    for (let i = index; i >= 0 && i < HERO_FRAME_COUNT; i += step) {
      const hit = frames.get(i);
      if (hit) return [hit, i];
    }
    return null;
  };

  const blendAt = (position: number): FrameBlend => {
    const clamped = Math.min(HERO_FRAME_COUNT - 1, Math.max(0, position));

    const before = seek(Math.floor(clamped), -1);
    if (!before) {
      // Nothing behind it yet — scrolled past the download on a cold cache.
      // Any still beats an empty canvas, and there is nothing to blend with.
      const ahead = seek(Math.ceil(clamped), 1);
      return { from: ahead?.[0] ?? null, to: null, t: 0 };
    }

    const [fromImage, fromIndex] = before;
    const after = seek(fromIndex + 1, 1);
    if (!after) return { from: fromImage, to: null, t: 0 };

    const [toImage, toIndex] = after;
    // Guard the divisor: seek() can only return toIndex > fromIndex, but a
    // zero would silently produce Infinity and blank the frame.
    const gap = toIndex - fromIndex;
    return {
      from: fromImage,
      to: toImage,
      t: gap > 0 ? Math.min(1, Math.max(0, (clamped - fromIndex) / gap)) : 0,
    };
  };

  return { count: HERO_FRAME_COUNT, ready, progress, frameAt, blendAt };
}
