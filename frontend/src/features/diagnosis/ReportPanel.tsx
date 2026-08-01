import { useEffect, useRef, useState } from 'react';
import { Download, FileText, MessageCircleQuestion, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { SkeletonText } from '@/components/ui/Skeleton';
import { fetchDiagnosisReport, markReportDownloaded } from '@/lib/api';
import type { DiagnosisReportData } from '@/lib/api';
import { generateReportPdf, REPORT_SECTIONS } from './generateReport';

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 90_000;

/** Elapsed-time messages, so a slow generation doesn't look like a hang. */
const PROGRESS: [number, string][] = [
  [0, 'Sending your diagnosis to the report engine…'],
  [8, 'Gathering treatment and prevention guidance…'],
  [20, 'Composing the full agronomic report…'],
  [40, 'Almost there — finalising the report…'],
];

type Phase = 'polling' | 'ready' | 'error' | 'timeout';

export function ReportPanel({
  reportId,
  crop,
  diseaseClass,
  onReportDownloaded,
}: {
  reportId: string;
  crop: string;
  diseaseClass: string;
  /** Downloading the report is what unlocks the follow-up assistant. */
  onReportDownloaded: () => void;
}) {
  const [phase, setPhase] = useState<Phase>('polling');
  const [data, setData] = useState<DiagnosisReportData | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [progress, setProgress] = useState(PROGRESS[0]?.[1] ?? 'Generating your report…');
  const [downloading, setDownloading] = useState(false);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    let cancelled = false;
    startedAt.current = Date.now();
    setPhase('polling');
    setData(null);

    const progressTimer = setInterval(() => {
      const elapsed = (Date.now() - startedAt.current) / 1000;
      for (let i = PROGRESS.length - 1; i >= 0; i -= 1) {
        const entry = PROGRESS[i];
        if (entry && elapsed >= entry[0]) {
          setProgress(entry[1]);
          break;
        }
      }
    }, 1000);

    const pollTimer = setInterval(async () => {
      if (cancelled) return;

      if (Date.now() - startedAt.current > POLL_TIMEOUT_MS) {
        setPhase('timeout');
        setMessage(
          'Report generation is taking longer than expected. The diagnosis above is still valid.',
        );
        clearInterval(pollTimer);
        clearInterval(progressTimer);
        return;
      }

      try {
        const result = await fetchDiagnosisReport(reportId);
        if (cancelled) return;

        if (result.status === 'ready') {
          setData(result.data ?? null);
          setPhase('ready');
          clearInterval(pollTimer);
          clearInterval(progressTimer);
        } else if (result.status === 'error' || result.status === 'not_found') {
          setPhase('error');
          setMessage(
            result.message ??
              'The report session expired. Run the diagnosis again to regenerate it.',
          );
          clearInterval(pollTimer);
          clearInterval(progressTimer);
        }
        // 'processing' simply continues polling.
      } catch {
        // Transient network blips shouldn't kill the poll; the timeout guard
        // above is what eventually ends it.
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(pollTimer);
      clearInterval(progressTimer);
    };
  }, [reportId]);

  async function handleDownload() {
    if (!data) return;
    setDownloading(true);
    try {
      await generateReportPdf(data, crop, diseaseClass);
      await markReportDownloaded(reportId).catch(() => {
        // The PDF already reached the user; a failed bookkeeping call must not
        // surface as a download error.
      });
      onReportDownloaded();
    } finally {
      setDownloading(false);
    }
  }

  if (phase === 'error' || phase === 'timeout') {
    return (
      <Card>
        <CardContent className="pt-5 sm:pt-6">
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" aria-hidden="true" />
          Full agronomic report
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-5">
        {phase === 'polling' ? (
          <div className="space-y-3" aria-live="polite" aria-busy="true">
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <FileText className="size-4 shrink-0 motion-safe:animate-pulse" aria-hidden="true" />
              {progress}
            </p>
            <SkeletonText lines={5} />
          </div>
        ) : (
          <>
            <dl className="space-y-4">
              {REPORT_SECTIONS.map(({ key, label }) => {
                const value = data?.[key];
                if (!value) return null;
                return (
                  <div key={key}>
                    <dt className="text-label uppercase tracking-wider text-primary">{label}</dt>
                    <dd className="mt-1 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
                      {value}
                    </dd>
                  </div>
                );
              })}
            </dl>

            <div className="flex flex-col gap-2 border-t border-border pt-4 sm:flex-row">
              <Button onClick={handleDownload} loading={downloading} loadingText="Preparing PDF…">
                <Download aria-hidden="true" />
                Download PDF report
              </Button>
            </div>

            <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
              <MessageCircleQuestion className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              Downloading the report unlocks the follow-up assistant, so you can ask questions about
              this specific diagnosis.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
