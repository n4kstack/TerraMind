import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Leaf, MessageCircleQuestion, ScanLine } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ConfidenceMeter } from '@/components/ui/ConfidenceMeter';
import { EmptyState, ErrorState, StagedLoader } from '@/components/ui/States';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { ImageDropzone } from '@/features/diagnosis/ImageDropzone';
import { ReportPanel } from '@/features/diagnosis/ReportPanel';
import { AssistantDrawer } from '@/features/diagnosis/AssistantDrawer';
import { useAsyncAction } from '@/hooks/useAsyncAction';
import { predictDiagnosis } from '@/lib/api';
import type { DiagnosisResponse } from '@/lib/api';
import { Reveal, RevealItem } from '@/components/ui/Reveal';
import { humanize } from '@/lib/utils';

const STAGES = [
  'Uploading your photograph',
  'Detecting leaf region',
  'Classifying against known disease classes',
  'Ranking the closest matches',
];

const TOP_K_OPTIONS = [
  { value: '1', label: 'Top 1' },
  { value: '3', label: 'Top 3' },
  { value: '5', label: 'Top 5' },
];

/**
 * "Healthy" is a real class in this model's label set, so it gets a distinct
 * positive treatment rather than being presented as though a disease was found.
 */
function isHealthy(className: string) {
  return className.toLowerCase().includes('healthy');
}

/** Class labels arrive like "Tomato___Late_blight". */
function prettyClass(raw: string) {
  return humanize(raw.replace(/_{2,}/g, ' — ').replace(/_/g, ' '));
}

function DiagnosisResults({ result }: { result: DiagnosisResponse }) {
  const healthy = isHealthy(result.identified_class);
  const alternatives = result.top_k_predictions?.slice(1) ?? [];

  return (
    <Reveal stagger className="space-y-5">
      <RevealItem>
        <Card elevated className="overflow-hidden">
          <div
            className={
              healthy
                ? 'border-b border-border bg-primary/[0.07] px-5 py-4 sm:px-6'
                : 'border-b border-border bg-destructive/[0.07] px-5 py-4 sm:px-6'
            }
          >
            <span
              className={
                healthy
                  ? 'flex items-center gap-2 text-label uppercase tracking-wider text-primary'
                  : 'flex items-center gap-2 text-label uppercase tracking-wider text-destructive'
              }
            >
              {healthy ? (
                <CheckCircle2 className="size-4" aria-hidden="true" />
              ) : (
                <AlertTriangle className="size-4" aria-hidden="true" />
              )}
              {healthy ? 'No disease detected' : 'Likely diagnosis'}
            </span>
          </div>

          <CardContent className="space-y-4 pt-5 sm:pt-6">
            <div>
              <Badge variant="neutral" className="mb-2 capitalize">
                <Leaf aria-hidden="true" />
                {result.identified_crop}
              </Badge>
              <h2 className="text-2xl font-extrabold tracking-tight text-foreground sm:text-3xl">
                {prettyClass(result.identified_class)}
              </h2>
            </div>

            <ConfidenceMeter value={result.confidence} />

            {/* A confident-looking single answer from an image classifier is the
                easiest way to mislead someone. Say plainly when it is unsure. */}
            {result.confidence < 0.6 && (
              <p className="flex items-start gap-2 rounded-md border border-accent/25 bg-accent/[0.07] p-3 text-xs leading-relaxed text-muted-foreground">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-accent" aria-hidden="true" />
                <span>
                  This match is weak. Retake the photo in daylight with a single leaf filling the
                  frame, or compare the alternatives below before treating.
                </span>
              </p>
            )}
          </CardContent>
        </Card>
      </RevealItem>

      {alternatives.length > 0 && (
        <RevealItem>
          <Card>
            <CardHeader>
              <CardTitle>Other possible matches</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {alternatives.map((prediction) => (
                <div key={prediction.class} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-foreground">
                      {prettyClass(prediction.class)}
                    </span>
                    <span className="tabular text-sm text-muted-foreground">
                      {Math.round(prediction.confidence * 100)}%
                    </span>
                  </div>
                  <ConfidenceMeter value={prediction.confidence} showLabel={false} size="sm" />
                </div>
              ))}
            </CardContent>
          </Card>
        </RevealItem>
      )}
    </Reveal>
  );
}

export default function Diagnosis() {
  const [file, setFile] = useState<File | null>(null);
  const [topK, setTopK] = useState('3');
  const [reportDownloaded, setReportDownloaded] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const { status, data, error, isOffline, run, reset } = useAsyncAction(predictDiagnosis);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (status !== 'success') return;
    if (window.matchMedia('(max-width: 1023px)').matches) {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [status]);

  const handleClear = useCallback(() => {
    setFile(null);
    setReportDownloaded(false);
    setAssistantOpen(false);
    reset();
  }, [reset]);

  const handleRun = useCallback(() => {
    if (!file) return;
    // Each new diagnosis invalidates the previous report gate.
    setReportDownloaded(false);
    setAssistantOpen(false);
    void run(file, Number(topK));
  }, [file, topK, run]);

  const assistantEnabled = status === 'success' && Boolean(data?.report_id) && reportDownloaded;

  return (
    <>
      <PageHeader
        icon={ScanLine}
        title="Disease diagnosis"
        description="Photograph an affected leaf and TerraMind will identify the most likely disease, with ranked alternatives and a confidence score for each."
        actions={
          assistantEnabled && data ? (
            <Button variant="outline" onClick={() => setAssistantOpen(true)}>
              <MessageCircleQuestion aria-hidden="true" />
              Ask about this
            </Button>
          ) : undefined
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
        <div className="lg:col-span-5">
          <div className="space-y-4 lg:sticky lg:top-24">
            <Card elevated>
              <CardContent className="space-y-5 pt-5 sm:pt-6">
                <ImageDropzone
                  file={file}
                  onSelect={setFile}
                  onClear={handleClear}
                  disabled={status === 'loading'}
                />

                <div className="space-y-1.5">
                  <span className="text-label text-foreground">Alternatives to show</span>
                  <SegmentedControl
                    label="Number of predictions to return"
                    options={TOP_K_OPTIONS}
                    value={topK}
                    onChange={setTopK}
                  />
                </div>

                <Button
                  type="button"
                  size="lg"
                  fullWidth
                  disabled={!file}
                  loading={status === 'loading'}
                  loadingText="Analysing photo…"
                  onClick={handleRun}
                >
                  <ScanLine aria-hidden="true" />
                  Diagnose this leaf
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>

        <div ref={resultsRef} className="scroll-mt-24 space-y-5 lg:col-span-7">
          {status === 'idle' && (
            <EmptyState
              icon={ScanLine}
              title="Your diagnosis will appear here"
              description="Add a clear photo of the affected leaf. A single leaf filling the frame, photographed in daylight against a plain background, gives the most reliable result."
            />
          )}
          {status === 'loading' && <StagedLoader stages={STAGES} title="Analysing your photo" />}
          {status === 'error' && (
            <ErrorState
              title={isOffline ? 'Cannot reach TerraMind' : 'Diagnosis failed'}
              message={error ?? 'Something went wrong.'}
              isOffline={isOffline}
              onRetry={file ? handleRun : undefined}
            />
          )}
          {status === 'success' && data && (
            <>
              <DiagnosisResults result={data} />
              {data.report_id && (
                <ReportPanel
                  reportId={data.report_id}
                  crop={data.identified_crop}
                  diseaseClass={data.identified_class}
                  onReportDownloaded={() => setReportDownloaded(true)}
                />
              )}
            </>
          )}
        </div>
      </div>

      {data?.report_id && (
        <AssistantDrawer
          open={assistantOpen}
          onClose={() => setAssistantOpen(false)}
          crop={data.identified_crop}
          diseaseClass={data.identified_class}
          reportId={data.report_id}
        />
      )}
    </>
  );
}
