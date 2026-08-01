import { lazy, Suspense } from 'react';
import {
  AlertTriangle,
  Award,
  BarChart3,
  Droplets,
  Info,
  MapPinned,
  Sun,
  TrendingDown,
  TrendingUp,
  Wheat,
  Zap,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { ConfidenceMeter } from '@/components/ui/ConfidenceMeter';
import { Reveal, RevealItem } from '@/components/ui/Reveal';
import { cn, humanize } from '@/lib/utils';
import type { AdvisorResponse } from '@/lib/api';

const YieldTrajectoryChart = lazy(() => import('./YieldTrajectoryChart'));

/**
 * Renders a "not recorded" marker rather than a zero.
 * Several district fields are legitimately null when no historical record
 * exists. Showing 0 t/ha for "unknown" would be a fabricated agronomic figure
 * (MASTER.md §5.2), so absence is always rendered explicitly.
 */
function Unavailable({ label = 'Not recorded for this district' }: { label?: string }) {
  return <span className="text-sm italic text-muted-foreground">{label}</span>;
}

function StatTile({
  icon: Icon,
  label,
  value,
  unit,
  hint,
}: {
  icon: typeof Sun;
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  hint?: string;
}) {
  const hasValue = value !== null && value !== undefined && value !== '';
  return (
    <div className="rounded-md border border-border bg-muted/40 p-4">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className="size-3.5 shrink-0" aria-hidden="true" />
        {label}
      </div>
      <div className="mt-2">
        {hasValue ? (
          <p className="tabular text-xl font-extrabold leading-none text-foreground">
            {value}
            {unit && <span className="ml-1 text-sm font-semibold text-muted-foreground">{unit}</span>}
          </p>
        ) : (
          <Unavailable label="Not available" />
        )}
      </div>
      {hint && <p className="mt-1.5 text-xs leading-snug text-muted-foreground">{hint}</p>}
    </div>
  );
}

/**
 * Cross-checks the model's yield against this district's own recorded history,
 * which arrives in the same response.
 *
 * This is not cosmetic. A live call for rice in Ludhiana returned
 * `expected_yield: 1041.028` labelled `t/ha`, while the district's real
 * trajectory in the same payload read 4.41–4.68 t/ha — the figure is roughly
 * two orders of magnitude out, because `unit` is hardcoded to "t/ha" in
 * backend/services/inference_pipeline.py while the model's training target is
 * on a different scale.
 *
 * The UI deliberately does NOT rescale the number: silently dividing a model
 * output by a guessed constant would be fabricating an agronomic figure. It
 * instead shows the value alongside an explicit disagreement warning, so the
 * reader can see that the two numbers cannot both be right.
 */
function checkYieldPlausibility(
  expected: number | null | undefined,
  history: number[] | undefined,
): { implausible: boolean; historicalRange?: string } {
  if (expected == null || !history || history.length === 0) return { implausible: false };
  const min = Math.min(...history);
  const max = Math.max(...history);
  if (max <= 0) return { implausible: false };

  const implausible = expected > max * 10 || expected < min / 10;
  return {
    implausible,
    historicalRange: `${min.toFixed(2)}–${max.toFixed(2)}`,
  };
}

export function AdvisorResults({ result }: { result: AdvisorResponse }) {
  const { crop_recommender, yield_predictor, agri_condition_advisor, district_intelligence } = result;

  const top = crop_recommender.top_3?.[0];
  const alternatives = crop_recommender.top_3?.slice(1) ?? [];
  const trajectory = district_intelligence.ten_year_trajectory_data;
  const trend = district_intelligence.yield_trend?.toLowerCase() ?? '';
  const TrendIcon = trend.includes('declin') || trend.includes('down') ? TrendingDown : TrendingUp;

  const yieldCheck = checkYieldPlausibility(yield_predictor.expected_yield, trajectory?.yields);

  return (
    <Reveal stagger className="space-y-5">
      {/* ---------------------------------------------------- Headline crop */}
      <RevealItem>
        <Card elevated className="overflow-hidden">
          <div className="border-b border-border bg-primary/[0.06] px-5 py-4 sm:px-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-label uppercase tracking-wider text-primary">
                <Award className="size-4" aria-hidden="true" />
                Recommended crop
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">
                  <Zap aria-hidden="true" />
                  {humanize(result.execution_mode)}
                </Badge>
                {result.adaptation_applied && <Badge variant="primary">Locally adapted</Badge>}
              </div>
            </div>
          </div>

          <CardContent className="pt-5 sm:pt-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <h2 className="text-4xl font-extrabold capitalize tracking-tight text-foreground">
                {crop_recommender.selected_crop || 'No recommendation'}
              </h2>
              {top && (
                <div className="min-w-[12rem] flex-1 sm:max-w-xs">
                  <ConfidenceMeter value={top.final_confidence} />
                </div>
              )}
            </div>

            {yield_predictor.explanation && (
              <p className="mt-4 text-base leading-relaxed text-muted-foreground">
                {yield_predictor.explanation}
              </p>
            )}

            {/* Local adaptation is the interesting part of this model: show how
                much the district prior moved the base confidence. */}
            {top && Math.abs(top.local_adjustment) > 0.0001 && (
              <p className="mt-3 flex items-start gap-2 rounded-md bg-muted/60 p-3 text-xs leading-relaxed text-muted-foreground">
                <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                <span>
                  Base model confidence was{' '}
                  <strong className="tabular text-foreground">
                    {Math.round(top.base_confidence * 100)}%
                  </strong>
                  ; local adaptation for this district adjusted it by{' '}
                  <strong className={cn('tabular', top.local_adjustment > 0 ? 'text-primary' : 'text-accent')}>
                    {top.local_adjustment > 0 ? '+' : ''}
                    {(top.local_adjustment * 100).toFixed(1)} pts
                  </strong>
                  .
                </span>
              </p>
            )}
          </CardContent>
        </Card>
      </RevealItem>

      {/* --------------------------------------------------- Yield + climate */}
      <RevealItem>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wheat className="size-4 text-primary" aria-hidden="true" />
              Expected yield & field conditions
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              icon={BarChart3}
              label="Expected yield"
              value={yield_predictor.expected_yield?.toFixed(2)}
              unit={yield_predictor.unit}
              hint={
                yield_predictor.confidence_band.lower != null &&
                yield_predictor.confidence_band.upper != null
                  ? `Range ${yield_predictor.confidence_band.lower.toFixed(2)}–${yield_predictor.confidence_band.upper.toFixed(2)}`
                  : undefined
              }
            />
            <StatTile
              icon={Sun}
              label="Sunlight"
              value={agri_condition_advisor.sunlight_hours?.toFixed(1)}
              unit="hrs/day"
            />
            <StatTile
              icon={Droplets}
              label="Irrigation"
              value={humanize(agri_condition_advisor.irrigation_type || '')}
              hint={agri_condition_advisor.irrigation_need || undefined}
            />
            <StatTile
              icon={MapPinned}
              label="District crop share"
              value={
                district_intelligence.district_crop_share_percent != null
                  ? `${district_intelligence.district_crop_share_percent}`
                  : null
              }
              unit={district_intelligence.district_crop_share_percent != null ? '%' : undefined}
            />
          </CardContent>

          {yieldCheck.implausible && (
            <CardContent className="pt-0">
              <p
                role="alert"
                className="flex items-start gap-2 rounded-md border border-destructive/25 bg-destructive/[0.07] p-3 text-xs leading-relaxed text-muted-foreground"
              >
                <AlertTriangle
                  className="mt-0.5 size-3.5 shrink-0 text-destructive"
                  aria-hidden="true"
                />
                <span>
                  <strong className="text-foreground">
                    This yield figure disagrees with your district's own records.
                  </strong>{' '}
                  Historical yields here range{' '}
                  <strong className="tabular text-foreground">{yieldCheck.historicalRange}</strong>{' '}
                  {yield_predictor.unit}, so the predicted value above is likely reported on a
                  different scale. Treat the crop recommendation as usable, but do not plan around
                  this yield number — use the district history below instead.
                </span>
              </p>
            </CardContent>
          )}

          {agri_condition_advisor.district_irrigation_summary && (
            <CardContent className="pt-0">
              <p className="rounded-md bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">
                {agri_condition_advisor.district_irrigation_summary}
              </p>
            </CardContent>
          )}
        </Card>
      </RevealItem>

      {/* ---------------------------------------------------- Alternatives */}
      {alternatives.length > 0 && (
        <RevealItem>
          <Card>
            <CardHeader>
              <CardTitle>Other viable crops</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {alternatives.map((entry) => (
                <div key={entry.crop} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold capitalize text-foreground">{entry.crop}</span>
                    <span className="tabular text-sm text-muted-foreground">
                      {Math.round(entry.final_confidence * 100)}%
                    </span>
                  </div>
                  <ConfidenceMeter value={entry.final_confidence} showLabel={false} size="sm" />
                </div>
              ))}
            </CardContent>
          </Card>
        </RevealItem>
      )}

      {/* ----------------------------------------------- District intelligence */}
      <RevealItem>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPinned className="size-4 text-primary" aria-hidden="true" />
              District intelligence
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {district_intelligence.yield_trend && (
              <div className="flex items-center gap-2 text-sm">
                <TrendIcon className="size-4 shrink-0 text-primary" aria-hidden="true" />
                <span className="text-foreground">{district_intelligence.yield_trend}</span>
              </div>
            )}

            {trajectory && trajectory.years?.length > 1 ? (
              <div>
                <Suspense fallback={<Skeleton className="h-56 w-full" />}>
                  <YieldTrajectoryChart
                    years={trajectory.years}
                    yields={trajectory.yields}
                    unit={yield_predictor.unit}
                  />
                </Suspense>
                {district_intelligence.ten_year_trajectory_summary && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {district_intelligence.ten_year_trajectory_summary}
                  </p>
                )}
              </div>
            ) : (
              <p className="rounded-md border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
                {district_intelligence.ten_year_trajectory_summary ||
                  'No historical yield trajectory for this crop in this district.'}
              </p>
            )}

            {district_intelligence.top_competing_crops &&
              district_intelligence.top_competing_crops.length > 0 && (
                <div>
                  <p className="mb-2 text-label uppercase tracking-wider text-muted-foreground">
                    Commonly grown here
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {district_intelligence.top_competing_crops.map((crop) => (
                      <Badge key={crop} variant="neutral" className="capitalize">
                        {crop}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

            {district_intelligence.irrigation_infrastructure_summary && (
              <div>
                <p className="mb-1.5 text-label uppercase tracking-wider text-muted-foreground">
                  Irrigation infrastructure
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {district_intelligence.irrigation_infrastructure_summary}
                </p>
              </div>
            )}

            {district_intelligence.best_historical_season && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Best historical season:</span>
                <Badge variant="success" className="capitalize">
                  {district_intelligence.best_historical_season}
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>
      </RevealItem>

      {/* ------------------------------------------------------ System notes */}
      {result.system_notes && result.system_notes.length > 0 && (
        <RevealItem>
          <details className="group rounded-lg border border-border bg-card">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 p-4 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground">
              <span className="flex items-center gap-2">
                <Info className="size-4" aria-hidden="true" />
                Model notes ({result.system_notes.length})
              </span>
              <span className="text-xs font-normal">
                {result.model_version}
                {result.latency_ms ? ` · ${Math.round(result.latency_ms)}ms` : ''}
              </span>
            </summary>
            <ul className="space-y-1.5 border-t border-border p-4 text-xs leading-relaxed text-muted-foreground">
              {result.system_notes.map((note, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-muted-foreground/50" aria-hidden="true">
                    •
                  </span>
                  {note}
                </li>
              ))}
            </ul>
          </details>
        </RevealItem>
      )}
    </Reveal>
  );
}
