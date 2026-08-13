import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  AlertOctagon,
  AlertTriangle,
  BookMarked,
  Bug,
  ListChecks,
  Network,
  Send,
  Sparkles,
  Square,
  User,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Card, CardContent } from '@/components/ui/Card';
import { ApiError, fetchAugNosisHealth, queryAugNosis } from '@/lib/api';
import type { AugNosisContext, AugNosisHealth } from '@/lib/api';
import { messageVariants } from '@/lib/motion';

const Markdown = lazy(() => import('@/components/ui/Markdown'));
import { cn, humanize } from '@/lib/utils';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  context?: AugNosisContext;
  failed?: boolean;
  /** Stopped by the user. Rendered as a quiet note, never as an error. */
  canceled?: boolean;
}

/**
 * Date.now() alone collides when two messages land in the same millisecond,
 * which duplicate React keys and drops a bubble from the transcript.
 */
let messageSeq = 0;
function nextId(role: 'u' | 'a'): string {
  messageSeq += 1;
  return `${role}-${Date.now()}-${messageSeq}`;
}

const SUGGESTIONS = [
  'Why are the lower leaves of my tomato plants turning yellow?',
  'When should I apply nitrogen to wheat?',
  'How do I manage stem borer in rice without heavy pesticide use?',
  'What causes blossom end rot, and can I still save the crop?',
];

/**
 * Knowledge-graph grounding, surfaced.
 *
 * AugNosis's value over a generic chatbot is that its answers are retrieved
 * from a knowledge graph. Hiding that leaves the user unable to tell a grounded
 * answer from an invented one, so any risk context returned alongside an answer
 * is shown with it (MASTER.md §5.3).
 */
/** Node ids arrive as slugs like "rice_stem_borer". */
function prettyNode(id: string): string {
  return humanize(id);
}

function ContextChips({ context }: { context: AugNosisContext }) {
  // Only genuinely string-valued fields may be rendered as chips. Rendering a
  // SoilConflict/TankMixWarning object here would throw at runtime.
  const riskGroups = [
    { items: context.high_risk_pests_now ?? [], icon: Bug, variant: 'caution' as const, key: 'pest' },
    {
      items: context.high_risk_diseases_now ?? [],
      icon: AlertOctagon,
      variant: 'risk' as const,
      key: 'disease',
    },
  ].filter((g) => g.items.length > 0);

  const urgent = context.urgent_actions ?? [];
  const soilConflicts = context.soil_conflicts ?? [];
  const tankMix = context.tank_mix_warnings ?? [];
  const sources = context.data_sources ?? [];
  const confidence = typeof context.confidence === 'string' ? context.confidence : null;

  const hasAnything =
    riskGroups.length > 0 ||
    urgent.length > 0 ||
    soilConflicts.length > 0 ||
    tankMix.length > 0 ||
    sources.length > 0;
  if (!hasAnything) return null;

  const confidenceVariant =
    confidence === 'high' ? 'success' : confidence === 'low' ? 'risk' : 'caution';

  return (
    <div className="mt-3 space-y-3 rounded-md border border-border bg-muted/40 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <Network className="size-3.5" aria-hidden="true" />
          Grounded in knowledge graph
        </p>
        {/* MASTER §5.1: retrieval confidence is never hidden. */}
        {confidence && (
          <Badge variant={confidenceVariant}>{humanize(confidence)} confidence</Badge>
        )}
      </div>

      {riskGroups.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {riskGroups.flatMap(({ items, icon: Icon, variant, key }) =>
            items.slice(0, 6).map((item) => (
              <Badge key={`${key}-${item}`} variant={variant}>
                <Icon aria-hidden="true" />
                {prettyNode(item)}
              </Badge>
            )),
          )}
        </div>
      )}

      {urgent.length > 0 && (
        <div>
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-foreground">
            <ListChecks className="size-3.5 text-accent" aria-hidden="true" />
            Act on this now
          </p>
          <ul className="space-y-1">
            {urgent.slice(0, 4).map((action) => (
              <li key={action} className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
                <span aria-hidden="true" className="text-accent">
                  •
                </span>
                {action}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Objects, formatted field-by-field rather than rendered directly. */}
      {soilConflicts.length > 0 && (
        <ul className="space-y-1">
          {soilConflicts.slice(0, 3).map((conflict, i) => (
            <li
              key={`soil-${i}`}
              className="flex gap-2 text-xs leading-relaxed text-muted-foreground"
            >
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-accent" aria-hidden="true" />
              <span>
                <strong className="text-foreground">{conflict.pesticide ?? 'A treatment'}</strong>
                {conflict.soil ? ` on ${humanize(conflict.soil)} soil` : ''}
                {conflict.reason ? `: ${conflict.reason}` : ''}
                {conflict.recommendation ? ` — ${conflict.recommendation}` : ''}
              </span>
            </li>
          ))}
        </ul>
      )}

      {tankMix.length > 0 && (
        <ul className="space-y-1">
          {tankMix.slice(0, 3).map((warning, i) => (
            <li
              key={`mix-${i}`}
              className="flex gap-2 text-xs leading-relaxed text-muted-foreground"
            >
              <AlertOctagon
                className="mt-0.5 size-3.5 shrink-0 text-destructive"
                aria-hidden="true"
              />
              <span>
                Do not tank-mix{' '}
                <strong className="text-foreground">{warning.pesticide_a ?? 'these'}</strong> with{' '}
                <strong className="text-foreground">{warning.pesticide_b ?? 'the other'}</strong>
                {warning.reason ? `: ${warning.reason}` : ''}
              </span>
            </li>
          ))}
        </ul>
      )}

      {/* MASTER §5.3: citing sources is the entire trust proposition here. */}
      {sources.length > 0 && (
        <div className="border-t border-border pt-2">
          <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
            <BookMarked className="size-3.5" aria-hidden="true" />
            Sources
          </p>
          <p className="text-xs leading-relaxed text-muted-foreground">{sources.join(' · ')}</p>
        </div>
      )}
    </div>
  );
}

function HealthPill({ health }: { health: AugNosisHealth | null }) {
  if (!health) return null;
  const ok = health.status === 'ok';
  return (
    <Badge variant={ok ? 'success' : 'caution'}>
      <span
        className={cn('size-1.5 rounded-full', ok ? 'bg-primary' : 'bg-accent')}
        aria-hidden="true"
      />
      {ok ? 'Assistant online' : 'Degraded'}
      {health.kg_nodes ? ` · ${health.kg_nodes.toLocaleString()} nodes` : ''}
    </Badge>
  );
}

export default function AugNosis() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [health, setHealth] = useState<AugNosisHealth | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    fetchAugNosisHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  // Navigating away mid-answer should not leave a request running.
  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, pending]);

  /**
   * Stop the in-flight answer, keeping whatever is already typed. The rejection
   * lands in `send`'s catch, which owns the transcript note and the pending
   * reset — so this only has to fire the abort.
   */
  function stop() {
    abortRef.current?.abort();
    textareaRef.current?.focus();
  }

  async function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed) return;

    // A new question supersedes whatever is in flight rather than being refused
    // — a 180s budget is far too long to make someone wait out an answer they
    // no longer want. Aborting *before* installing the new controller is what
    // makes this safe: the superseded request's handlers find a ref that no
    // longer points at them and bow out without touching state, so only the
    // newest question ever writes to the transcript or clears `pending`.
    const superseded = abortRef.current !== null;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const isCurrent = () => abortRef.current === controller;

    setMessages((prev) => [
      ...prev,
      // Close the abandoned answer off here, synchronously, rather than from its
      // own rejection handler: that runs a tick later, by which point the new
      // question is already on screen and the note would attach to the wrong one.
      ...(superseded
        ? [{ id: nextId('a'), role: 'assistant' as const, content: 'Response stopped.', canceled: true }]
        : []),
      { id: nextId('u'), role: 'user' as const, content: trimmed },
    ]);
    setInput('');
    setPending(true);

    try {
      const result = await queryAugNosis(trimmed, { signal: controller.signal });
      if (!isCurrent()) return;
      setMessages((prev) => [
        ...prev,
        {
          id: nextId('a'),
          role: 'assistant',
          content: result.response || 'No answer was returned for that question.',
          context: result.context,
        },
      ]);
    } catch (error) {
      if (!isCurrent()) return;
      // Superseding aborts never reach here (the ref check above catches them),
      // so a cancellation at this point was the Stop button: note it quietly.
      if (error instanceof ApiError && error.isCanceled) {
        setMessages((prev) => [
          ...prev,
          { id: nextId('a'), role: 'assistant', content: 'Response stopped.', canceled: true },
        ]);
        return;
      }
      setMessages((prev) => [
        ...prev,
        {
          id: nextId('a'),
          role: 'assistant',
          content:
            error instanceof Error
              ? error.message
              : 'The assistant could not be reached. Please try again.',
          failed: true,
        },
      ]);
    } finally {
      if (isCurrent()) {
        abortRef.current = null;
        setPending(false);
        textareaRef.current?.focus();
      }
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter makes a new line. Standard for chat, and avoids
    // trapping users who expect Enter to submit.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  }

  return (
    <>
      <PageHeader
        icon={Network}
        title="AugNosis"
        description="Ask a farming question in plain language. Answers are retrieved from an agricultural knowledge graph, and any pest, disease or soil risks it finds are shown alongside."
        actions={<HealthPill health={health} />}
      />

      <Card elevated className="flex h-[calc(100dvh-19rem)] min-h-[30rem] flex-col overflow-hidden">
        {/* role=log + aria-live so new answers are announced as they arrive. */}
        <div
          className="flex-1 space-y-5 overflow-y-auto p-4 sm:p-6"
          role="log"
          aria-live="polite"
          aria-label="Conversation"
        >
          {messages.length === 0 && !pending && (
            <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
              <span className="grid size-16 place-items-center rounded-xl bg-primary/10 text-primary">
                <Sparkles className="size-8" aria-hidden="true" />
              </span>
              <div className="max-w-md space-y-2">
                <h2 className="text-h2 text-foreground">What would you like to know?</h2>
                <p className="text-base leading-relaxed text-muted-foreground">
                  Ask about a symptom you're seeing, a treatment you're considering, or the timing of
                  an operation.
                </p>
              </div>
              <ul className="grid w-full max-w-2xl gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((suggestion) => (
                  <li key={suggestion}>
                    <button
                      type="button"
                      onClick={() => void send(suggestion)}
                      className="h-full w-full cursor-pointer rounded-md border border-border bg-card p-3 text-left text-sm leading-snug text-muted-foreground transition-colors duration-150 hover:border-primary/30 hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                    >
                      {suggestion}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <AnimatePresence initial={false}>
            {messages.map((message) => (
              <motion.div
                key={message.id}
                {...(reduced
                  ? {}
                  : {
                      variants: messageVariants(message.role),
                      initial: 'initial' as const,
                      animate: 'animate' as const,
                    })}
                className={cn('flex gap-3', message.role === 'user' && 'flex-row-reverse')}
              >
                <span
                  className={cn(
                    'grid size-8 shrink-0 place-items-center rounded-md',
                    message.role === 'user'
                      ? 'bg-muted text-muted-foreground'
                      : 'bg-primary/10 text-primary',
                  )}
                  aria-hidden="true"
                >
                  {message.role === 'user' ? (
                    <User className="size-4" />
                  ) : (
                    <Sparkles className="size-4" />
                  )}
                </span>

                <div className={cn('min-w-0 max-w-[85%]', message.role === 'user' && 'text-right')}>
                  <span className="sr-only">
                    {message.role === 'user' ? 'You said:' : 'AugNosis replied:'}
                  </span>
                  <div
                    className={cn(
                      'inline-block rounded-lg px-4 py-3 text-left text-sm leading-relaxed',
                      message.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : message.failed
                          ? 'border border-destructive/25 bg-destructive/[0.07] text-foreground'
                          : message.canceled
                            ? // Stopping was intentional, so this reads as a status
                              // line rather than something that went wrong.
                              'border border-dashed border-border italic text-muted-foreground'
                            : 'border border-border bg-muted/50 text-foreground',
                    )}
                  >
                    {message.role === 'assistant' && !message.failed && !message.canceled ? (
                      <Suspense
                        fallback={<span className="whitespace-pre-wrap">{message.content}</span>}
                      >
                        <Markdown>{message.content}</Markdown>
                      </Suspense>
                    ) : (
                      message.content
                    )}
                  </div>

                  {message.context && <ContextChips context={message.context} />}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {pending && (
            <div className="flex gap-3">
              <span
                className="grid size-8 shrink-0 place-items-center rounded-md bg-primary/10 text-primary"
                aria-hidden="true"
              >
                <Sparkles className="size-4" />
              </span>
              <div className="flex items-center gap-1.5 rounded-lg border border-border bg-muted/50 px-4 py-4">
                {/* Three-dot typing indicator. */}
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="size-2 rounded-full bg-muted-foreground/60"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.18 }}
                  />
                ))}
                <span className="sr-only">AugNosis is thinking</span>
              </div>
            </div>
          )}

          <div ref={endRef} />
        </div>

        <CardContent className="border-t border-border p-3 sm:p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(input);
            }}
            className="flex items-end gap-2"
          >
            <label htmlFor="augnosis-input" className="sr-only">
              Ask a farming question
            </label>
            <textarea
              id="augnosis-input"
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about a symptom, treatment or timing…"
              className="max-h-32 min-h-[2.75rem] flex-1 resize-none rounded-md border border-border-input bg-card px-3.5 py-3 text-base text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/25"
            />
            {/* Shown alongside Send rather than replacing it: stopping and
                asking something else are different intentions, and while an
                answer is generating a user may want either. */}
            {pending && (
              <Button
                type="button"
                size="icon"
                variant="outline"
                onClick={stop}
                aria-label="Stop generating the current answer"
              >
                {/* Smaller than the icon-button default: a solid stop glyph
                    reads better at 14px than filling the whole 20px box. */}
                <Square className="size-3.5 fill-current" aria-hidden="true" />
              </Button>
            )}
            <Button
              type="submit"
              size="icon"
              disabled={!input.trim()}
              aria-label={pending ? 'Stop the current answer and ask this instead' : 'Send question'}
            >
              <Send aria-hidden="true" />
            </Button>
          </form>
          {/* The disclaimer stays put while generating — a safety notice is not
              something to swap out for a transient hint. */}
          {pending && (
            <p className="mt-2 px-1 text-xs text-muted-foreground">
              Generating — stop to cancel, or send a new question to replace it.
            </p>
          )}
          <p className="mt-2 px-1 text-xs text-muted-foreground">
            AugNosis can be wrong. Verify treatments against local agronomic guidance before acting.
          </p>
        </CardContent>
      </Card>
    </>
  );
}
