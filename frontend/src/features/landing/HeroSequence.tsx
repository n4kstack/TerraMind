import { useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  easeInOut,
  motion,
  useMotionValue,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from 'framer-motion';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { cn } from '@/lib/utils';
import { ScrollFrameCanvas } from './ScrollFrameCanvas';
import { HERO_STATS } from './heroCopy';

/**
 * The landing hero, as a pinned scroll act.
 *
 * A tall track holds a sticky, viewport-sized stage. While the track scrolls
 * past, the stage stays put and the footage advances one still per scroll
 * position; three beats of copy hand off across it. When the track runs out the
 * stage unpins and the rest of the page continues normally.
 *
 * Copy sits on the footage as near-white on a dark scrim in BOTH themes, which
 * is a departure from every other surface in this app. It is deliberate. The
 * rest of the site controls its own background and can guarantee contrast
 * against it; here the background is photography whose luminance varies frame
 * to frame, and light-mode's dark-green-on-near-white cannot be made to clear
 * AA over it without scrimming the footage down to nothing — which would defeat
 * the point of shipping footage. Fixing the copy to light-on-dark makes the
 * contrast a property of the scrim, which we control, rather than of whichever
 * frame happens to be showing. Everything below the hero returns to the theme.
 */

/**
 * Track height as a multiple of the viewport. The sticky stage eats one
 * viewport of it, so the sequence is scrubbed across (TRACK - 1) screens of
 * scroll. At 3.4 that is ~2.4 screens: long enough that the footage reads as
 * motion rather than a slideshow, short enough that a reader who wants the
 * modules list is not trapped in the hero.
 */
const TRACK_VH = 3.4;

/**
 * Length of a beat's fade, as a fraction of the pin.
 *
 * The beat windows below are chosen so that each one's fade-OUT starts exactly
 * where the next one's fade-IN does — `to - BEAT_FADE === next.from`. That makes
 * the two halves of every hand-off complementary: one line is arriving at the
 * same rate the other is leaving, and the pair sums to roughly full strength
 * throughout.
 *
 * The first pass did not line them up, and it showed. Beat one finished fading
 * at 0.34 while beat two only began at 0.30, so there was a stretch with one
 * line at half strength and the next still at nothing — a visible dip to bare
 * footage between every pair of lines.
 *
 * 0.10 of a 2.4-screen pin is about 230px of scroll per fade.
 */
const BEAT_FADE = 0.1;

/** [from, to] per beat. Adjacent entries overlap by exactly BEAT_FADE. */
const BEATS = {
  intro: [0, 0.36],
  season: [0.26, 0.7],
  coverage: [0.6, 1],
} as const;

/**
 * The one heading style every beat uses.
 *
 * A constant rather than three copies of the same classes, because three copies
 * is exactly how this went wrong: the beats drifted to 56px, 72px and 36px —
 * the closing line barely half the size of the middle one — and read as three
 * unrelated slides rather than one continuous piece. Sizing lives here so a
 * change to one beat cannot silently fail to reach the others.
 *
 * 72px at the top end because the middle beat is the constraint: it is one
 * phrase on a full screen of footage with nothing else competing, and anything
 * smaller reads as a caption. The other two carry more furniture but hold the
 * size comfortably.
 *
 * The phone step is 1.75rem, and getting there took measuring rather than
 * guessing. These headings break their own lines, and while they did it with
 * <br> a phrase that outgrew the screen could only spill: at 2.1rem on a 390px
 * screen "When something goes wrong." needed 362px against 358px available and
 * dropped a lone "wrong." onto a fourth line. `text-balance` could not repair
 * it, because a <br> ends the block it balances over.
 *
 * Each phrase is its own `block` span now, so balance applies per phrase and a
 * phrase too long for the screen splits into two even lines instead of
 * orphaning its last word. That decouples the size from the narrowest phone —
 * chasing a no-wrap fit would have meant ~1.45rem to survive a 360px screen,
 * which is small for the one line the whole hero is built around.
 */
const BEAT_HEADING =
  'text-balance text-[1.75rem] font-extrabold leading-[1.1] tracking-[-0.02em] text-white ' +
  'drop-shadow-[0_2px_24px_rgba(0,0,0,0.5)] sm:text-6xl lg:text-7xl';

/**
 * Measure for every beat, shared for the same reason as the size above.
 *
 * 5xl, not the 3xl the beats used to default to: at 72px the longest lines
 * ("before you plant it.", "When something goes wrong.") run past 768px and
 * wrap mid-phrase, which breaks the deliberate line rhythm each beat is written
 * around.
 */
const BEAT_MEASURE = 'max-w-5xl';

interface BeatProps {
  progress: MotionValue<number>;
  /** Window within the pin, 0..1, over which this beat owns the stage. */
  from: number;
  to: number;
  /**
   * Measure for this beat's content. Defaults to the 3xl the prose beats want;
   * a beat set in display sizes needs more room or it wraps mid-phrase.
   */
  width?: string;
  children: ReactNode;
}

/**
 * One stage of hero copy, cross-fading with its neighbours.
 *
 * Beats overlap by design: `to` of one runs past `from` of the next, so the
 * outgoing line is still dissolving as the incoming one arrives. Cutting them
 * cleanly reads as a slide change; overlapping them reads as one continuous
 * shot.
 */
function Beat({ progress, from, to, width = 'max-w-3xl', children }: BeatProps) {
  const fade = Math.min(BEAT_FADE, (to - from) / 3);

  // The first beat is on screen at rest and the last stays put once reached, so
  // neither gets an entrance or an exit at the sequence boundary. Only the
  // interior edges animate.
  const opens = from > 0;
  const closes = to < 1;

  const stops = [
    ...(opens ? [from, from + fade] : [0]),
    ...(closes ? [to - fade, to] : [1]),
  ];
  const alpha = [...(opens ? [0, 1] : [1]), ...(closes ? [1, 0] : [1])];

  // A small counter-drift so copy moves against the footage rather than sitting
  // welded to the glass. Transform only — never `top` — so it stays off the
  // layout path during scroll.
  const y = useTransform(progress, [from, to], [opens ? 44 : 0, closes ? -44 : 0], {
    clamp: true,
  });
  // Eased rather than linear. A linear cross-fade spends most of its length in
  // the muddy middle where both beats are half-lit and neither is comfortably
  // readable; easing both ends compresses that and gives each line more of its
  // window at full strength.
  const opacity = useTransform(progress, stops, alpha, { clamp: true, ease: easeInOut });

  // A faded-out beat is still in the DOM, and `opacity: 0` hides it from
  // exactly one audience: people looking at it. Its links stay in the tab
  // order, stay clickable, and stay in the accessibility tree — so a keyboard
  // user scrolled to the last beat would tab into an invisible "Start with your
  // field" button belonging to the first. `visibility: hidden` fixes all three
  // at once, and is discrete rather than animated, so the threshold has to sit
  // low enough that the switch happens while the beat is already imperceptible.
  const visibility = useTransform(opacity, (value) => (value < 0.04 ? 'hidden' : 'visible'));
  // Separate, higher threshold for hit-testing: mid-cross-fade both beats are
  // half-lit, and the outgoing one should stop swallowing clicks well before it
  // finishes disappearing.
  const pointerEvents = useTransform(opacity, (value) => (value < 0.55 ? 'none' : 'auto'));

  return (
    // inset-0 + items-center, not inset-x-0. Beats used to be absolutely
    // positioned with no vertical anchor, which resolves to their static
    // position — the top of a zero-height wrapper sitting at the middle of the
    // stage. So every beat hung *downwards from* the centre rather than being
    // centred on it. Short prose got away with it; the first beat tall enough
    // to notice ran off the bottom of the viewport with its last line cut in
    // half. Filling the stage and centring inside it is correct for any height.
    <motion.div
      style={{ opacity, y, visibility, pointerEvents }}
      className="absolute inset-0 flex items-center px-4 text-center sm:px-6 lg:px-8"
    >
      <div className={cn('mx-auto w-full', width)}>{children}</div>
    </motion.div>
  );
}

/** Everything that is not the footage: copy, CTAs, cue. */
function Stage({ progress, ready }: { progress: MotionValue<number>; ready: boolean }) {
  // Fades on the first flick of the wheel — a cue that is still pointing down
  // after the user has already scrolled is noise.
  const cueOpacity = useTransform(progress, [0, 0.05], [1, 0], { clamp: true });

  return (
    <>
      {/* The three beats share one well so they overlap in place rather than
          pushing each other around during the cross-fade. Each beat now fills
          this box and centres its own content, so the well itself needs no
          layout — it is only a stacking context and a pointer-events barrier.
          Inert by default; each beat re-enables hit-testing for itself only
          while it is actually legible. */}
      <div className="pointer-events-none absolute inset-0 z-10">
        <div className="relative size-full">
          <Beat progress={progress} from={BEATS.intro[0]} to={BEATS.intro[1]} width={BEAT_MEASURE}>
            <h1 className={BEAT_HEADING}>
              <span className="block">Know what to plant,</span>
              <span className="block text-hero-accent">before you plant it.</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-relaxed text-white/85 drop-shadow-[0_1px_12px_rgba(0,0,0,0.5)] sm:text-lg">
              TerraMind turns soil readings, local climate and a district's agricultural history
              into decisions you can act on.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button asChild size="lg" className="w-full sm:w-auto">
                <Link to="/advisor">
                  Start with your field
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
              {/* No backdrop-blur anywhere in this hero, deliberately. A
                  backdrop filter forces the compositor to re-snapshot and blur
                  the region beneath it, and the region beneath this one is a
                  canvas being redrawn on every scroll frame — it is the most
                  expensive possible place to put one. Chrome also keeps
                  painting a backdrop filter for elements the beat has set to
                  `visibility: hidden`, which left a grey ghost rectangle of the
                  faded-out beat sitting over the footage. A flat translucent
                  fill costs nothing and there is already a scrim behind it. */}
              <Button
                asChild
                size="lg"
                variant="outline"
                className="w-full border-white/40 bg-white/15 text-white hover:bg-white/25 hover:text-white sm:w-auto"
              >
                <Link to="/augnosis">Ask a farming question</Link>
              </Button>
            </div>
          </Beat>

          {/* Deliberately does not restate the closing section's copy. The
              middle beat is the one the reduced-motion still cannot carry, so
              it holds editorial phrasing rather than any fact or claim that
              only exists here. */}
          {/* Set larger than the opening beat, not smaller. This is the only
              beat carrying no sub-copy, no buttons and no cards — it is one
              phrase on a full screen of footage, and at the h1's size it read as
              a caption. `max-w-5xl` because "When something goes wrong." is 25
              characters of display type and wraps mid-phrase inside 3xl, which
              breaks the three-line rhythm the line depends on. */}
          <Beat progress={progress} from={BEATS.season[0]} to={BEATS.season[1]} width={BEAT_MEASURE}>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-hero-accent drop-shadow-[0_1px_10px_rgba(0,0,0,0.5)] sm:text-sm">
              One field, the whole season
            </p>
            <h2 className={cn(BEAT_HEADING, 'mt-5')}>
              <span className="block">Before you sow.</span>
              <span className="block">While it grows.</span>
              <span className="block text-hero-accent">When something goes wrong.</span>
            </h2>
          </Beat>

          <Beat progress={progress} from={BEATS.coverage[0]} to={BEATS.coverage[1]} width={BEAT_MEASURE}>
            <h2 className={BEAT_HEADING}>
              Grounded in real coverage
            </h2>
            <ul className="mx-auto mt-10 grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3">
              {HERO_STATS.map(({ value, label, icon: Icon }) => (
                <li
                  key={label}
                  className="flex items-center gap-4 rounded-lg border border-white/15 bg-hero-void/55 p-5 text-left"
                >
                  <span className="grid size-11 shrink-0 place-items-center rounded-md bg-white/15 text-hero-accent">
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="tabular text-2xl font-extrabold leading-none text-white">
                      {value}
                    </p>
                    <p className="mt-1 text-xs font-medium text-white/75">{label}</p>
                  </div>
                </li>
              ))}
            </ul>
          </Beat>
        </div>
      </div>

      {/* Held back until the first still has decoded. A cue inviting someone to
          scroll through footage that has not arrived yet points at nothing.

          Gated with `invisible` rather than a CSS opacity transition: opacity
          here is already driven continuously from scroll, and layering a
          `transition-opacity` on top means every scroll frame restarts a 500ms
          interpolation toward a target that has already moved. Measured, the
          cue never converged — it sat at 0.77 two full seconds after a scroll
          to 78%, where the transform says 0, and stayed painted over the
          footage for the whole act. */}
      <motion.div
        style={{ opacity: cueOpacity }}
        className={cn(
          'pointer-events-none absolute inset-x-0 bottom-8 z-10 flex flex-col items-center gap-2 text-white/70',
          ready ? 'visible' : 'invisible',
        )}
        aria-hidden="true"
      >
        <span className="text-[0.7rem] font-semibold uppercase tracking-[0.2em]">Scroll</span>
        <ChevronDown className="size-4 animate-bounce" />
      </motion.div>
    </>
  );
}

/**
 * Reduced-motion hero: the same copy, no pin, no scrub, no footage.
 *
 * Not a degraded variant of the animated one — a plain section that renders
 * everything at full opacity with no dependency on any animation completing.
 * The three beats collapse into one block, because with nothing to scrub they
 * are just three paragraphs.
 */
function StillHero() {
  return (
    <section className="relative">
      <div className="mx-auto max-w-7xl px-4 pb-24 pt-16 sm:px-6 sm:pt-24 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-balance text-4xl font-extrabold leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-display">
            Know what to plant,
            <br />
            <span className="text-primary">before you plant it.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-relaxed text-foreground dark:text-muted-foreground sm:text-lg">
            TerraMind turns soil readings, local climate and a district's agricultural history into
            decisions you can act on — crop choice, expected yield, fertiliser dosage, and disease
            diagnosis from a single photograph.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="w-full sm:w-auto">
              <Link to="/advisor">
                Start with your field
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="w-full sm:w-auto">
              <Link to="/augnosis">Ask a farming question</Link>
            </Button>
          </div>
        </div>

        <ul className="mx-auto mt-16 grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3">
          {HERO_STATS.map(({ value, label, icon: Icon }) => (
            <li
              key={label}
              className="flex items-center gap-4 rounded-lg border border-border bg-card p-5 shadow-sm"
            >
              <span className="grid size-11 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <div>
                <p className="tabular text-2xl font-extrabold leading-none text-foreground">
                  {value}
                </p>
                <p className="mt-1 text-xs font-medium text-muted-foreground">{label}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function HeroSequence() {
  const trackRef = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const compact = useMediaQuery('(max-width: 639px)');
  const [ready, setReady] = useState(false);

  // `start start` -> `end end`: 0 the moment the stage pins, 1 the moment the
  // track's bottom edge reaches the viewport's, which is also the moment the
  // stage unpins. The mapping is exact, so the last still lands precisely as
  // the hero lets go.
  const { scrollYProgress } = useScroll({
    target: trackRef,
    offset: ['start start', 'end end'],
  });

  /**
   * Relayed through a plain MotionValue rather than used directly, and this is
   * load-bearing.
   *
   * When an opacity in `style` traces back to useScroll unbroken, Framer hands
   * it to the browser as a native scroll-linked WAAPI animation. That path does
   * not agree with the value Framer computes in JS: measured at 78% through the
   * pin, the scroll cue's own transform said 0 while `getComputedStyle` said
   * 0.77 and the cue was plainly still painted over the footage — its animation
   * object held the right keyframes (1 -> 0 by offset 0.05) driven from a
   * timeline reading ~0.01. String-valued transforms are not eligible for that
   * optimisation, so `visibility` stayed correct throughout, which is the only
   * reason the beats looked right: they were being cut, not faded.
   *
   * A MotionValue written by JS is not a scroll timeline Framer can hand off,
   * so everything downstream renders from the value it actually computed.
   */
  const relayed = useMotionValue(0);
  useMotionValueEvent(scrollYProgress, 'change', (value) => relayed.set(value));

  /**
   * Smoothing, and the single thing that decides whether this reads as footage
   * or as a flipbook.
   *
   * Scroll input is not continuous. One wheel notch is a ~100px jump, which at
   * this track length is five stills at once — bound directly, the canvas
   * teleports across them and shows none of the motion in between. The spring
   * turns each notch into a short animation *through* those frames, so the
   * footage moves even though the input did not.
   *
   * Tuned by damping ratio, not by feel. This is a scrubber, not a parallax
   * toy: the picture has to stay attached to the scrollbar, and the two failure
   * modes are opposite. Under ~0.85 the spring overshoots, which on a scrubber
   * means the footage runs past where you stopped and walks backwards to meet
   * you — the one artefact nobody reads as "smooth". Over ~1.15 it goes
   * sluggish, and the lag reads as the page being slow.
   *
   *     zeta = damping / (2 * sqrt(stiffness * mass))
   *
   * These give zeta 1.07 and settle in ~225ms: just past critical, so it is
   * guaranteed monotonic — no overshoot at any scroll speed — while still
   * spreading a wheel notch over roughly a dozen rendered frames.
   *
   * The first pass shipped 190/34/0.28, which is zeta 2.33 and ~680ms. Measured
   * against a single wheel notch it sat still for the first 120ms and was
   * visibly still moving 400ms later.
   *
   * restDelta is small because at the end of a 120-still sequence the last
   * fraction of a percent of progress is still most of a frame.
   */
  const progress = useSpring(relayed, {
    stiffness: 170,
    damping: 14,
    mass: 0.25,
    restDelta: 0.00002,
  });

  // Ramps in over the closing sixth of the pin — early enough that the edge is
  // already soft when the stage starts moving, late enough that the footage is
  // untouched for the whole act.
  const handoff = useTransform(progress, [0.84, 1], [0, 1], { clamp: true });

  if (reduced) return <StillHero />;

  return (
    <div
      ref={trackRef}
      className="relative"
      style={{
        height: `${TRACK_VH * 100}svh`,
        // Pull the track up under the navbar so the footage starts at the very
        // top of the viewport. The bar is `sticky`, not `fixed`, so it occupies
        // 4rem of normal flow plus its 1px transparent bottom border; without
        // this the stage sits 65px down and its own bottom 65px — the scroll
        // cue — falls off the screen. Navbar recolours itself while this hero
        // is behind it (see #hero-end below).
        marginTop: 'calc(-4rem - 1px)',
      }}
    >
      {/* h-svh, not h-dvh: a sticky stage sized to the *dynamic* viewport
          resizes every time a mobile URL bar slides, which reflows and clears
          the canvas mid-gesture. The small viewport is stable. */}
      <div className="sticky top-0 h-svh w-full overflow-hidden bg-hero-void">
        <div className="absolute inset-0">
          <ScrollFrameCanvas
            progress={progress}
            compact={compact}
            onReadyChange={setReady}
          />
        </div>

        {/* Legibility scrim: constant, because the copy needs its contrast at
            every scroll position. */}
        <div className="hero-frame-scrim pointer-events-none absolute inset-0" aria-hidden="true" />

        {/* The handoff into the page, faded in by scroll rather than painted
            constantly. Left on, it washes the bottom third of every frame to
            near-background and the footage reads as hazy from the first
            moment — for a seam that does not exist until the stage is about to
            unpin. Nothing is below the stage until then. */}
        <motion.div
          style={{ opacity: handoff }}
          className="hero-frame-fade pointer-events-none absolute inset-0"
          aria-hidden="true"
        />

        <Stage progress={progress} ready={ready} />
      </div>

      {/* Marker, not a spacer. Navbar watches for this id to decide whether it
          is currently floating over footage — while it is, the bar drops its
          background and switches to light-on-dark. Keeping the signal in the
          DOM rather than in shared state means every other route gets the
          normal bar for free, by the element simply not being there. */}
      <div id="hero-end" className="pointer-events-none absolute bottom-0 h-px w-full" />
    </div>
  );
}
