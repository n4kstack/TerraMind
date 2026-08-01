import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { Ban, MessageCircleQuestion, Send, Sparkles, User, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { askDiagnosisAssistant } from '@/lib/api';
import { messageVariants } from '@/lib/motion';
import { cn } from '@/lib/utils';

const Markdown = lazy(() => import('@/components/ui/Markdown'));

interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  /** false when the backend declined the question as out of scope. */
  allowed?: boolean;
  reason?: string;
}

/**
 * Follow-up assistant for a specific diagnosis.
 *
 * A slide-over rather than a route so the user keeps the diagnosis on screen
 * while asking about it. Focus is moved into the panel on open and restored to
 * the trigger on close, and Escape dismisses it — a drawer that traps keyboard
 * users is worse than no drawer.
 */
export function AssistantDrawer({
  open,
  onClose,
  crop,
  diseaseClass,
  reportId,
}: {
  open: boolean;
  onClose: () => void;
  crop: string;
  diseaseClass: string;
  reportId: string;
}) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<Element | null>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (open) {
      triggerRef.current = document.activeElement;
      // Defer so the element exists once the panel has mounted.
      requestAnimationFrame(() => inputRef.current?.focus());
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
      (triggerRef.current as HTMLElement | null)?.focus?.();
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, pending]);

  async function send() {
    const question = input.trim();
    if (!question || pending) return;

    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: 'user', text: question }]);
    setInput('');
    setPending(true);
    setError(null);

    try {
      const result = await askDiagnosisAssistant({
        question,
        top_k: 5,
        identified_crop: crop,
        identified_class: diseaseClass,
        report_id: reportId,
      });
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          text: result.answer,
          allowed: result.allowed,
          reason: result.reason,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The assistant could not be reached.');
    } finally {
      setPending(false);
      inputRef.current?.focus();
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-foreground/20 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={`Assistant for ${crop} diagnosis`}
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 34 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-card shadow-xl"
          >
            <header className="flex items-start justify-between gap-3 border-b border-border p-4">
              <div className="min-w-0">
                <h2 className="flex items-center gap-2 text-h3 text-foreground">
                  <Sparkles className="size-4 text-primary" aria-hidden="true" />
                  Ask about this diagnosis
                </h2>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">
                  {crop} · {diseaseClass.replace(/_{2,}/g, ' — ').replace(/_/g, ' ')}
                </p>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close assistant">
                <X aria-hidden="true" />
              </Button>
            </header>

            <div
              className="flex-1 space-y-4 overflow-y-auto p-4"
              role="log"
              aria-live="polite"
              aria-label="Assistant conversation"
            >
              {messages.length === 0 && !pending && (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                  <MessageCircleQuestion className="size-10 text-muted-foreground/40" aria-hidden="true" />
                  <p className="max-w-xs text-sm text-muted-foreground">
                    Ask about treatment options, how quickly to act, or what to watch for next.
                  </p>
                </div>
              )}

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
                  className={cn('flex gap-2.5', message.role === 'user' && 'flex-row-reverse')}
                >
                  <span
                    className={cn(
                      'grid size-7 shrink-0 place-items-center rounded-md',
                      message.role === 'user'
                        ? 'bg-muted text-muted-foreground'
                        : 'bg-primary/10 text-primary',
                    )}
                    aria-hidden="true"
                  >
                    {message.role === 'user' ? (
                      <User className="size-3.5" />
                    ) : (
                      <Sparkles className="size-3.5" />
                    )}
                  </span>
                  <div
                    className={cn(
                      'min-w-0 rounded-lg px-3.5 py-2.5 text-sm leading-relaxed',
                      message.role === 'user'
                        ? 'max-w-[85%] bg-primary text-primary-foreground'
                        : message.allowed === false
                          ? // A refused answer is one short sentence, so it keeps
                            // the inset bubble; a real answer takes the full width
                            // it needs for headings, lists and tables to read.
                            'max-w-[85%] border border-accent/25 bg-accent/[0.07] text-foreground'
                          : 'flex-1 border border-border bg-muted/50 text-foreground',
                    )}
                  >
                    {message.allowed === false && (
                      <span className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-accent">
                        <Ban className="size-3.5" aria-hidden="true" />
                        Outside this diagnosis
                      </span>
                    )}
                    {message.role === 'assistant' && message.allowed !== false ? (
                      // Answers come back as markdown. Rendered as plain text the
                      // newlines collapse and the whole reply becomes one block.
                      <Suspense
                        fallback={<span className="whitespace-pre-wrap">{message.text}</span>}
                      >
                        <Markdown>{message.text}</Markdown>
                      </Suspense>
                    ) : (
                      message.text
                    )}
                    {message.allowed === false && message.reason && (
                      <span className="mt-1.5 block text-xs text-muted-foreground">
                        {message.reason}
                      </span>
                    )}
                  </div>
                </motion.div>
              ))}

              {pending && (
                <div className="flex items-center gap-1.5 px-2" aria-label="Assistant is thinking">
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className="size-2 rounded-full bg-muted-foreground/60"
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.18 }}
                    />
                  ))}
                </div>
              )}

              {error && (
                <p role="alert" className="text-sm font-medium text-destructive">
                  {error}
                </p>
              )}

              <div ref={endRef} />
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
              className="flex items-center gap-2 border-t border-border p-3"
            >
              <label htmlFor="assistant-input" className="sr-only">
                Ask a question about this diagnosis
              </label>
              <input
                id="assistant-input"
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question…"
                className="h-11 flex-1 rounded-md border border-border-input bg-background px-3.5 text-base text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/25"
              />
              <Button type="submit" size="icon" disabled={!input.trim() || pending} aria-label="Send">
                <Send aria-hidden="true" />
              </Button>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
