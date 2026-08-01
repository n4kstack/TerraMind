import { Link } from 'react-router-dom';
import { ArrowRight, Leaf, MapPin, Layers, ShieldCheck, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { NAV_ITEMS } from '@/components/layout/navigation';
import { Reveal, RevealItem } from '@/components/ui/Reveal';
import stateDistrictMapping from '@/data/state_district_mapping.json';

/**
 * Landing page.
 *
 * Body copy that sits directly on the animated backdrop uses --foreground in
 * light mode rather than --muted-foreground. This is legibility, not taste:
 * light mode puts mid-grey copy on a near-white surface, so a green leaf lands
 * between the two and closes the contrast gap from both sides. Measured, that
 * copy could not clear WCAG AA at any backdrop strength worth having — the tree
 * had to be scrimmed down to a ghost to save it. Darkening the copy instead
 * buys back the backdrop. Dark mode has no such problem and keeps the muted
 * tone. Copy that sits on a card is untouched.
 *
 * Every figure quoted here is derived from something real in this repository --
 * the bundled district map, the module list, the model pipeline. Nothing is
 * invented. Fabricated social proof ("trusted by 10,000 farmers") would be both
 * dishonest and, for an advisory tool that influences spending decisions,
 * actively harmful to trust.
 */

const districtMap = stateDistrictMapping as Record<string, string[]>;
const STATE_COUNT = Object.keys(districtMap).length;
const DISTRICT_COUNT = Object.values(districtMap).reduce((sum, list) => sum + list.length, 0);

const STATS = [
  { value: `${STATE_COUNT}`, label: 'States & UTs covered', icon: MapPin },
  { value: `${DISTRICT_COUNT}`, label: 'Districts with local priors', icon: Layers },
  { value: `${NAV_ITEMS.length}`, label: 'Intelligence modules', icon: Sparkles },
];

const STEPS = [
  {
    title: 'Describe your field',
    body: 'Enter soil nutrients, pH, local climate and your district. No account, no setup, no jargon.',
  },
  {
    title: 'Models run on your inputs',
    body: 'Ensemble crop and yield models combine your readings with district-level historical patterns.',
  },
  {
    title: 'Act on a clear recommendation',
    body: 'Every result states its confidence, so you know how much weight to give it before you spend.',
  },
];

function Hero() {
  return (
    // The backdrop moved to <LandingBackdrop>, mounted from <Layout> as a
    // sibling of <main>: the growth scene is fixed, and a fixed element nested
    // under <main> resolves against main's transform during the route
    // transition instead of the viewport.
    <section className="relative">
      {/* Deeper bottom padding than the other sections: it is the stage the
          seedling stands in before the first scroll. */}
      <div className="mx-auto max-w-7xl px-4 pb-28 pt-16 sm:px-6 sm:pt-24 lg:px-8 lg:pb-40">
        <Reveal stagger className="mx-auto max-w-3xl text-center">
          <RevealItem className="flex justify-center">
            <Badge variant="primary" className="px-3 py-1.5">
              <Leaf aria-hidden="true" />
              Smart Farming — Every Stage
            </Badge>
          </RevealItem>

          <RevealItem
            as="h1"
            className="mt-6 text-balance text-4xl font-extrabold leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-display"
          >
            Know what to plant,
            <br />
            <span className="text-primary">before you plant it.</span>
          </RevealItem>

          <RevealItem
            as="p"
            className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-relaxed text-foreground dark:text-muted-foreground sm:text-lg"
          >
            TerraMind turns soil readings, local climate and {DISTRICT_COUNT} districts of
            agricultural history into decisions you can act on — crop choice, expected yield,
            fertiliser dosage, and disease diagnosis from a single photograph.
          </RevealItem>

          <RevealItem
            className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row"
          >
            <Button asChild size="lg" className="w-full sm:w-auto">
              <Link to="/advisor">
                Start with your field
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="w-full sm:w-auto">
              <Link to="/augnosis">Ask a farming question</Link>
            </Button>
          </RevealItem>

          <RevealItem as="p" className="mt-4 text-xs text-foreground dark:text-muted-foreground">
            Free to use · No sign-up required
          </RevealItem>
        </Reveal>

        {/* Real, verifiable figures only. */}
        <Reveal
          stagger
          inView
          as="ul"
          className="mx-auto mt-16 grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3"
        >
          {STATS.map(({ value, label, icon: Icon }) => (
            // Glass rather than the opaque .card-surface: on short viewports
            // this row lands where the seedling stands, and an opaque card
            // would hide it completely at scroll 0. --card and --background sit
            // close in luminance in both themes, so text contrast is unchanged.
            <RevealItem
              key={label}
              as="li"
              className="flex items-center gap-4 rounded-lg border border-border bg-card/70 p-5 shadow-sm backdrop-blur-sm"
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
            </RevealItem>
          ))}
        </Reveal>
      </div>
    </section>
  );
}

function Modules() {
  return (
    <section className="border-t border-border bg-card/40">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
        <Reveal inView className="mx-auto max-w-2xl text-center">
          <h2 className="text-balance text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
            Four modules, one field
          </h2>
          <p className="mt-4 text-pretty leading-relaxed text-foreground dark:text-muted-foreground">
            Each covers a different point in the season. Use the one that matches where your crop is
            right now.
          </p>
        </Reveal>

        <Reveal stagger inView as="ul" className="mt-12 grid gap-5 sm:grid-cols-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon, description }, index) => (
            <RevealItem key={to} as="li">
              <Link
                to={to}
                className="group flex h-full flex-col gap-4 rounded-lg border border-border bg-card p-6 shadow-sm transition-[box-shadow,border-color,transform] duration-200 ease-organic hover:-translate-y-1 hover:border-primary/30 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="grid size-12 place-items-center rounded-lg bg-primary/10 text-primary transition-transform duration-200 ease-organic group-hover:scale-110">
                    <Icon className="size-6" aria-hidden="true" />
                  </span>
                  <span className="tabular text-xs font-bold text-muted-foreground">
                    0{index + 1}
                  </span>
                </div>
                <div className="space-y-2">
                  <h3 className="text-h3 text-foreground">{label}</h3>
                  <p className="text-base leading-relaxed text-muted-foreground">{description}</p>
                </div>
                <span className="mt-auto inline-flex items-center gap-1.5 pt-2 text-sm font-semibold text-primary">
                  Open {label}
                  <ArrowRight
                    className="size-4 transition-transform duration-200 ease-organic group-hover:translate-x-1"
                    aria-hidden="true"
                  />
                </span>
              </Link>
            </RevealItem>
          ))}
        </Reveal>
      </div>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
      <Reveal inView className="mx-auto max-w-2xl text-center">
        <h2 className="text-balance text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
          Three steps, no training required
        </h2>
      </Reveal>

      <Reveal stagger inView as="ol" className="mt-12 grid gap-8 md:grid-cols-3">
        {STEPS.map((step, index) => (
          <RevealItem key={step.title} as="li" className="relative">
            <span className="tabular grid size-11 place-items-center rounded-md bg-primary text-lg font-extrabold text-primary-foreground shadow-sm">
              {index + 1}
            </span>
            <h3 className="mt-4 text-h3 text-foreground">{step.title}</h3>
            <p className="mt-2 text-base leading-relaxed text-foreground dark:text-muted-foreground">
              {step.body}
            </p>
          </RevealItem>
        ))}
      </Reveal>
    </section>
  );
}

function TrustNote() {
  return (
    <section className="border-t border-border bg-card/40">
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <Reveal
          inView
          className="flex flex-col items-start gap-5 rounded-xl border border-border bg-card p-6 sm:flex-row sm:p-8"
        >
          <span className="grid size-12 shrink-0 place-items-center rounded-lg bg-accent/10 text-accent">
            <ShieldCheck className="size-6" aria-hidden="true" />
          </span>
          <div className="space-y-2">
            <h2 className="text-h3 text-foreground">Every prediction shows its confidence</h2>
            <p className="text-base leading-relaxed text-muted-foreground">
              These are statistical models, not certainties. TerraMind states how confident each
              result is and cites its sources in the AI assistant, so you can judge how much weight
              to give a recommendation. Treat all outputs as advisory and check them against local
              agronomic guidance before committing seed, fertiliser or money.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export default function Landing() {
  return (
    <>
      <Hero />
      <Modules />
      <HowItWorks />
      <TrustNote />
    </>
  );
}
