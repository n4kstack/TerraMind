/**
 * The living gradient behind the landing page.
 *
 * Deliberately CSS-only. Every layer here animates `transform` and `opacity`
 * on long, offset, non-harmonic cycles, so the browser can promote each to its
 * own compositor layer and the whole field costs nothing on the main thread —
 * which matters because it shares the page with the scroll-driven growth scene,
 * and that one does need the main thread.
 *
 * The cycle lengths (34s / 42s / 38s / 26s) are mutually prime enough that the
 * composition never visibly repeats. Motion this slow should register as the
 * light changing, not as an animation playing.
 */
export function AuroraField() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-20 overflow-hidden" aria-hidden="true">
      <div className="aurora-blob motion-safe:animate-drift-a absolute -left-[18%] -top-[24%] size-[34rem] bg-primary/[0.14] sm:size-[56rem]" />
      <div className="aurora-blob motion-safe:animate-drift-b absolute -right-[20%] top-[4%] size-[30rem] bg-secondary/[0.11] sm:size-[46rem]" />
      <div className="aurora-blob motion-safe:animate-drift-c absolute -bottom-[26%] left-[18%] size-[32rem] bg-accent/[0.07] sm:size-[52rem]" />

      {/* A slow diagonal sweep across the blobs — the "light shifting" pass.
          Blending the two greens rather than adding a fourth colour keeps the
          field agricultural instead of iridescent. */}
      <div className="aurora-wash motion-safe:animate-aurora-wash absolute inset-0" />

      {/* Pollen. Six motes, hidden on phones where they are a cost with no
          payoff at that size. Much fainter in light mode: a mid-green dot on a
          near-white surface is high contrast against the surface but LOW
          contrast against grey body copy, and these drift straight through the
          hero paragraph — measured, a single mote behind that paragraph was
          the worst pixel on the page in BOTH themes. Held low enough that one
          sitting under a glyph still leaves the copy above AA. */}
      <div className="absolute inset-0 hidden sm:block">
        {MOTES.map((mote, i) => (
          <span
            key={i}
            className="motion-safe:animate-mote-rise absolute size-1 rounded-full bg-primary/12 dark:bg-primary/25"
            style={{
              left: mote.left,
              top: mote.top,
              animationDelay: mote.delay,
              animationDuration: mote.duration,
            }}
          />
        ))}
      </div>
    </div>
  );
}

/** Hand-placed rather than random so the drift reads as scattered but never
 *  clumps two motes on the same track. */
const MOTES = [
  { left: '12%', top: '62%', delay: '0s', duration: '21s' },
  { left: '27%', top: '78%', delay: '-7s', duration: '26s' },
  { left: '46%', top: '68%', delay: '-14s', duration: '23s' },
  { left: '63%', top: '82%', delay: '-4s', duration: '28s' },
  { left: '78%', top: '58%', delay: '-18s', duration: '24s' },
  { left: '89%', top: '74%', delay: '-11s', duration: '30s' },
] as const;
