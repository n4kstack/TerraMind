import { Link } from 'react-router-dom';
import { ArrowRight, Sparkles } from 'lucide-react';
import { NAV_ITEMS } from '@/components/layout/navigation';
import { Reveal, RevealItem } from '@/components/ui/Reveal';
import { HeroSequence } from '@/features/landing/HeroSequence';
import { DISTRICT_COUNT } from '@/features/landing/heroCopy';

/**
 * Landing page.
 *
 * The hero is a pinned scroll act driven by a frame sequence — see
 * HeroSequence.tsx. Everything below it is ordinary themed page: no backdrop
 * canvas, no scrim, no contrast workarounds. That is the point of confining the
 * footage to one section. The previous design floated an aurora, a growth scene
 * and a leaf canopy behind the *whole* page, and every block of copy on it had
 * to be darkened or scrimmed to survive them.
 *
 * Every figure quoted here is derived from something real in this repository --
 * the bundled district map, the module list, the model pipeline. Nothing is
 * invented. Fabricated social proof ("trusted by 10,000 farmers") would be both
 * dishonest and, for an advisory tool that influences spending decisions,
 * actively harmful to trust.
 */

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

function Modules() {
  return (
    // field-transition begins on exactly the colour the hero's fade ends on, so
    // the join between footage and page has no edge to see. It is on this
    // section because this is the one that touches the hero.
    <section className="field-transition">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
        <Reveal inView className="mx-auto max-w-2xl text-center">
          <h2 className="text-balance text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
            Four modules, one field
          </h2>
          <p className="mt-4 text-pretty leading-relaxed text-muted-foreground">
            Each covers a different point in the season. Use the one that matches where your crop is
            right now.
          </p>
        </Reveal>

        <Reveal stagger inView as="ul" className="mt-12 grid gap-5 sm:grid-cols-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon, description }, index) => (
            <RevealItem key={to} as="li">
              <Link
                to={to}
                className="card-gradient card-gradient-hover group flex h-full flex-col gap-4 rounded-lg border border-border p-6 transition-[box-shadow,border-color,transform,background-image] duration-200 ease-organic hover:-translate-y-1 hover:border-primary/40 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="grid size-12 place-items-center rounded-lg bg-gradient-to-br from-primary/25 to-primary/5 text-primary ring-1 ring-inset ring-primary/15 transition-transform duration-200 ease-organic group-hover:scale-110">
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
            <p className="mt-2 text-base leading-relaxed text-muted-foreground">{step.body}</p>
          </RevealItem>
        ))}
      </Reveal>
    </section>
  );
}

function SeasonNote() {
  return (
    <section>
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <Reveal
          inView
          className="card-gradient flex flex-col items-start gap-5 rounded-xl border border-border p-6 sm:flex-row sm:p-8"
        >
          <span className="grid size-12 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-accent/25 to-accent/5 text-accent ring-1 ring-inset ring-accent/15">
            <Sparkles className="size-6" aria-hidden="true" />
          </span>
          <div className="space-y-2">
            <h2 className="text-h3 text-foreground">Most tools stop at a single prediction</h2>
            <p className="text-base leading-relaxed text-muted-foreground">
              TerraMind stays with the crop across {DISTRICT_COUNT} districts: ensemble models pick
              what to sow and forecast the yield, in-season guidance tunes fertiliser and flags pest
              pressure, a single leaf photograph names a disease, and a knowledge-graph assistant
              answers what to do next — with its sources. No account, no hardware, no training.
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
      <HeroSequence />
      <Modules />
      <HowItWorks />
      <SeasonNote />
    </>
  );
}
