import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

/**
 * Repair list markup the model glued onto a single line.
 *
 * The RAG models occasionally answer with `… measures: * **Pruning:** … * **Shade:** …`
 * instead of putting each bullet on its own line. CommonMark only starts a list
 * at the beginning of a line, so that renders as one unreadable paragraph.
 * Both repairs below are deliberately conservative — they fire only on shapes
 * that cannot plausibly be anything else, because a false positive would shred
 * legitimate prose.
 */
function repairInlineLists(input: string): string {
  let text = input.replace(/\r\n?/g, '\n').trim();

  // Escaped newlines that survived a JSON round trip somewhere upstream.
  if (!text.includes('\n') && text.includes('\\n')) {
    text = text.replace(/\\n/g, '\n');
  }

  const hasRealList = /^[ \t]*(?:[*+-]|\d+[.)])[ \t]+\S/m.test(text);

  // Bulleted: only an asterisk padded by spaces on both sides. Emphasis markers
  // (`*Lecanicillium lecanii*`) never have a space on their inner side, and `-`
  // is excluded entirely because it is far more often a dash than a bullet.
  if (!hasRealList) {
    const glued = / +\* +(?=\S)/g;
    if ((text.match(glued) ?? []).length >= 2) {
      text = text.replace(glued, '\n- ');
    }
  }

  // Numbered: require a complete ascending run starting at 1, so "apply 2. 5 L"
  // and similar stray decimals cannot trigger it.
  if (!/^[ \t]*\d+[.)][ \t]+\S/m.test(text)) {
    const markers = [...text.matchAll(/ (\d{1,2})[.)] +(?=\S)/g)];
    const ascending =
      markers.length >= 3 && markers.every((m, i) => Number(m[1]) === i + 1);
    if (ascending) {
      text = text.replace(/ (\d{1,2})[.)] +(?=\S)/g, (_m, n: string) => `\n${n}. `);
    }
  }

  return text;
}

/**
 * Wide content must scroll inside its own box rather than stretching the
 * message bubble past the panel edge.
 */
const components: Components = {
  table: ({ children }) => (
    <div className="my-2 max-w-full overflow-x-auto">
      <table className="my-0">{children}</table>
    </div>
  ),
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer noopener">
      {children}
    </a>
  ),
};

/**
 * Markdown renderer, isolated so it can be code-split.
 *
 * react-markdown + remark-gfm are ~156 kB and were previously pulled into the
 * AugNosis route chunk (163 kB total). Nothing can render until the assistant
 * replies — a measured 70s round trip — so loading the renderer up front bought
 * nothing. Split out, it is fetched while the user is already waiting.
 *
 * Typography is tuned for chat bubbles, not article bodies: prose's default
 * vertical rhythm leaves gaps wide enough to look like separate messages.
 */
export default function Markdown({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'prose prose-sm max-w-none text-foreground dark:prose-invert',
        // Blocks: tightened so a list reads as one answer, not five paragraphs.
        'prose-p:my-2 prose-p:leading-relaxed prose-p:text-foreground',
        'prose-headings:mb-1.5 prose-headings:mt-4 prose-headings:font-semibold prose-headings:text-foreground',
        'prose-h1:text-base prose-h2:text-[0.9375rem] prose-h3:text-sm prose-h4:text-sm',
        'prose-ul:my-2 prose-ul:pl-5 prose-ol:my-2 prose-ol:pl-5',
        'prose-li:my-1 prose-li:pl-0.5 prose-li:text-foreground prose-li:marker:text-primary',
        'prose-hr:my-3 prose-hr:border-border',
        // Inline
        'prose-strong:font-semibold prose-strong:text-foreground',
        'prose-em:text-foreground',
        'prose-a:font-medium prose-a:text-primary prose-a:underline prose-a:underline-offset-2',
        'prose-blockquote:border-l-2 prose-blockquote:border-primary/40 prose-blockquote:py-0 prose-blockquote:pl-3 prose-blockquote:not-italic prose-blockquote:text-muted-foreground',
        // Prose wraps inline code in literal backticks via ::before/::after;
        // with a background chip that reads as a typo.
        'prose-code:rounded prose-code:bg-foreground/[0.07] prose-code:px-1 prose-code:py-0.5 prose-code:text-[0.85em] prose-code:font-medium prose-code:text-foreground prose-code:before:content-none prose-code:after:content-none',
        'prose-pre:my-2 prose-pre:border prose-pre:border-border prose-pre:bg-foreground/[0.05] prose-pre:text-foreground',
        'prose-table:my-0 prose-th:text-foreground prose-td:text-foreground',
        // Long crop/chemical names and URLs must not push the bubble wider.
        'break-words',
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {repairInlineLists(children)}
      </ReactMarkdown>
    </div>
  );
}
