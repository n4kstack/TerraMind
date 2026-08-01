import { useCallback, useEffect, useRef } from 'react';
import { Sprout } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState, ErrorState, StagedLoader } from '@/components/ui/States';
import { AdvisorForm } from '@/features/advisor/AdvisorForm';
import { AdvisorResults } from '@/features/advisor/AdvisorResults';
import { useAsyncAction } from '@/hooks/useAsyncAction';
import { predictAdvisor, type AdvisorRequest } from '@/lib/api';

/** Descriptive of the actual server-side pipeline, not invented filler. */
const STAGES = [
  'Normalising soil and climate inputs',
  'Running the crop recommendation ensemble',
  'Estimating yield and confidence band',
  'Applying district-level historical priors',
  'Composing your advisory',
];

export default function Advisor() {
  const { status, data, error, isOffline, run } = useAsyncAction(predictAdvisor);
  const resultsRef = useRef<HTMLDivElement>(null);
  const lastPayload = useRef<AdvisorRequest | null>(null);

  const handleSubmit = useCallback(
    (payload: AdvisorRequest) => {
      lastPayload.current = payload;
      void run(payload);
    },
    [run],
  );

  // On phones the results sit below the form, off-screen. Without this the
  // submit appears to do nothing. Desktop is a two-column layout where the
  // results are already visible, so scrolling there would be disorienting.
  useEffect(() => {
    if (status !== 'success') return;
    const isStacked = window.matchMedia('(max-width: 1023px)').matches;
    if (isStacked) {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [status]);

  return (
    <>
      <PageHeader
        icon={Sprout}
        title="Pre-sowing advisor"
        description="Enter your soil readings, local climate and district. TerraMind combines them with historical patterns for your area to recommend a crop and estimate its yield."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
        <div className="lg:col-span-5">
          <div className="lg:sticky lg:top-24">
            <AdvisorForm onSubmit={handleSubmit} loading={status === 'loading'} />
          </div>
        </div>

        <div ref={resultsRef} className="scroll-mt-24 lg:col-span-7">
          {status === 'idle' && (
            <EmptyState
              icon={Sprout}
              title="Your advisory will appear here"
              description="Fill in the field profile and TerraMind will recommend a crop, estimate its yield, and show how your district has performed historically."
            />
          )}

          {status === 'loading' && <StagedLoader stages={STAGES} title="Analysing your field" />}

          {status === 'error' && (
            <ErrorState
              title={isOffline ? 'Cannot reach TerraMind' : 'Analysis failed'}
              message={error ?? 'Something went wrong.'}
              isOffline={isOffline}
              onRetry={
                lastPayload.current ? () => void run(lastPayload.current as AdvisorRequest) : undefined
              }
            />
          )}

          {status === 'success' && data && <AdvisorResults result={data} />}
        </div>
      </div>
    </>
  );
}
