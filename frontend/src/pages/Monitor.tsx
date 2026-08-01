import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Bug,
  CalendarClock,
  CheckCircle2,
  Droplets,
  FlaskConical,
  Layers,
  Scale,
  Sprout,
  Thermometer,
  TrendingUp,
  Wheat,
  Wind,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Combobox } from '@/components/ui/Combobox';
import { Field, FieldLabel, NumericInput } from '@/components/ui/Field';
import { EmptyState, ErrorState, StagedLoader } from '@/components/ui/States';
import { useAsyncAction } from '@/hooks/useAsyncAction';
import { predictMonitor, MONITOR_CROP_TYPES, MONITOR_SOIL_TYPES } from '@/lib/api';
import type { MonitorRequest, MonitorResponse } from '@/lib/api';
import { MONITOR_RULES, validateNumeric, type FieldErrors } from '@/features/advisor/validation';
import { Reveal, RevealItem } from '@/components/ui/Reveal';
import { cn } from '@/lib/utils';

type NumericKey = keyof typeof MONITOR_RULES;

const NUMERIC_FIELDS: { key: NumericKey; label: string; icon: typeof Thermometer }[] = [
  { key: 'temperature', label: 'Temperature', icon: Thermometer },
  { key: 'humidity', label: 'Humidity', icon: Wind },
  { key: 'moisture', label: 'Soil moisture', icon: Droplets },
  { key: 'N', label: 'Nitrogen', icon: FlaskConical },
  { key: 'P', label: 'Phosphorus', icon: FlaskConical },
  { key: 'K', label: 'Potassium', icon: FlaskConical },
  { key: 'ph', label: 'Soil pH', icon: FlaskConical },
  { key: 'rainfall', label: 'Rainfall', icon: Droplets },
];

const STAGES = [
  'Reading current field conditions',
  'Classifying growth stage and pest pressure',
  'Matching fertiliser and dosage',
  'Projecting post-application yield',
];

/**
 * Pest level arrives as a free-text label from the model. Mapping is done by
 * substring so an unexpected label degrades to "neutral" rather than crashing
 * or, worse, silently rendering a severe reading as safe.
 */
function pestSeverity(level: string): { variant: 'success' | 'caution' | 'risk' | 'neutral'; Icon: typeof Bug } {
  const l = level.toLowerCase();
  if (l.includes('low') || l.includes('none') || l.includes('minimal')) {
    return { variant: 'success', Icon: CheckCircle2 };
  }
  if (l.includes('moderate') || l.includes('medium')) return { variant: 'caution', Icon: AlertTriangle };
  if (l.includes('high') || l.includes('severe')) return { variant: 'risk', Icon: Bug };
  return { variant: 'neutral', Icon: Bug };
}

function MonitorResults({ result }: { result: MonitorResponse }) {
  const { variant, Icon } = pestSeverity(result.pest_level);

  return (
    <Reveal stagger className="space-y-5">
      <RevealItem>
        <Card elevated className="overflow-hidden">
          <div className="border-b border-border bg-primary/[0.06] px-5 py-4 sm:px-6">
            <span className="flex items-center gap-2 text-label uppercase tracking-wider text-primary">
              <Sprout className="size-4" aria-hidden="true" />
              Recommended fertiliser
            </span>
          </div>
          <CardContent className="pt-5 sm:pt-6">
            <h2 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
              {result.recommended_fertilizer}
            </h2>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Badge variant={variant}>
                <Icon aria-hidden="true" />
                Pest pressure: {result.pest_level}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </RevealItem>

      <RevealItem>
        <Card>
          <CardHeader>
            <CardTitle>Application plan</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-md border border-border bg-muted/40 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Scale className="size-3.5" aria-hidden="true" />
                Dosage
              </div>
              <p className="tabular mt-2 text-2xl font-extrabold leading-none text-foreground">
                {result.dosage}
                <span className="ml-1 text-sm font-semibold text-muted-foreground">kg/acre</span>
              </p>
            </div>

            <div className="rounded-md border border-border bg-muted/40 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <CalendarClock className="size-3.5" aria-hidden="true" />
                Apply after
              </div>
              <p className="tabular mt-2 text-2xl font-extrabold leading-none text-foreground">
                {result.apply_after_days}
                <span className="ml-1 text-sm font-semibold text-muted-foreground">
                  {result.apply_after_days === 1 ? 'day' : 'days'}
                </span>
              </p>
            </div>

            <div className="rounded-md border border-primary/25 bg-primary/[0.07] p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary">
                <TrendingUp className="size-3.5" aria-hidden="true" />
                Projected yield
              </div>
              <p className="tabular mt-2 text-2xl font-extrabold leading-none text-foreground">
                {result.expected_yield_after_dosage.toFixed(1)}
                <span className="ml-1 text-sm font-semibold text-muted-foreground">q/ha</span>
              </p>
              <p className="mt-1.5 text-xs text-muted-foreground">After applying this dosage</p>
            </div>
          </CardContent>
        </Card>
      </RevealItem>

      <RevealItem>
        <p className="flex items-start gap-2 rounded-lg border border-accent/25 bg-accent/[0.07] p-4 text-xs leading-relaxed text-muted-foreground">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
          <span>
            Dosage is a model estimate for the conditions you entered. Confirm against your
            fertiliser's label rate and local extension guidance before applying — over-application
            damages both the crop and the soil.
          </span>
        </p>
      </RevealItem>
    </Reveal>
  );
}

export default function Monitor() {
  const { status, data, error, isOffline, run } = useAsyncAction(predictMonitor);
  const resultsRef = useRef<HTMLDivElement>(null);
  const lastPayload = useRef<MonitorRequest | null>(null);

  const [values, setValues] = useState<Record<NumericKey, string>>({
    temperature: '',
    humidity: '',
    moisture: '',
    N: '',
    P: '',
    K: '',
    ph: '',
    rainfall: '',
  });
  const [cropType, setCropType] = useState<string | null>(null);
  const [soilType, setSoilType] = useState<string | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (status !== 'success') return;
    if (window.matchMedia('(max-width: 1023px)').matches) {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [status]);

  const setValue = useCallback(
    (key: NumericKey, raw: string) => {
      setValues((prev) => ({ ...prev, [key]: raw }));
      if (touched[key]) {
        setErrors((prev) => ({ ...prev, [key]: validateNumeric(raw, MONITOR_RULES[key]) }));
      }
    },
    [touched],
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const next: Record<string, string | null> = {};
    (Object.keys(MONITOR_RULES) as NumericKey[]).forEach((key) => {
      next[key] = validateNumeric(values[key], MONITOR_RULES[key]);
    });
    if (!cropType) next.crop_type = 'Select a crop';
    if (!soilType) next.soil_type = 'Select a soil type';

    const cleaned = Object.fromEntries(Object.entries(next).filter(([, v]) => v)) as Record<
      string,
      string
    >;
    setErrors(cleaned);
    setTouched(Object.fromEntries(Object.keys(MONITOR_RULES).map((k) => [k, true])));

    if (Object.keys(cleaned).length > 0) {
      const firstKey = Object.keys(cleaned)[0];
      document
        .querySelector<HTMLElement>(`[data-field="${firstKey}"] input, [data-field="${firstKey}"] button`)
        ?.focus();
      return;
    }

    const payload: MonitorRequest = {
      temperature: Number(values.temperature),
      humidity: Number(values.humidity),
      moisture: Number(values.moisture),
      soil_type: soilType as string,
      crop_type: cropType as string,
      N: Number(values.N),
      P: Number(values.P),
      K: Number(values.K),
      ph: Number(values.ph),
      rainfall: Number(values.rainfall),
    };
    lastPayload.current = payload;
    void run(payload);
  }

  return (
    <>
      <PageHeader
        icon={Activity}
        title="In-season monitor"
        description="For a crop already in the ground. Enter current field readings to get a fertiliser recommendation, dosage, application timing and pest-pressure assessment."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
        <div className="lg:col-span-5">
          <div className="lg:sticky lg:top-24">
            <Card elevated>
              <CardContent className="pt-5 sm:pt-6">
                <form onSubmit={handleSubmit} noValidate className="space-y-6">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div data-field="crop_type">
                      <Field error={errors.crop_type ?? null}>
                        <FieldLabel>
                          <>
                            <Wheat className="size-3.5 text-muted-foreground" aria-hidden="true" />
                            Crop
                          </>
                        </FieldLabel>
                        <Combobox
                          options={[...MONITOR_CROP_TYPES]}
                          value={cropType}
                          onChange={(v) => {
                            setCropType(v);
                            setErrors((p) => ({ ...p, crop_type: undefined }));
                          }}
                          placeholder="Select crop"
                          searchPlaceholder="Search crops…"
                        />
                      </Field>
                    </div>

                    <div data-field="soil_type">
                      <Field error={errors.soil_type ?? null}>
                        <FieldLabel>
                          <>
                            <Layers className="size-3.5 text-muted-foreground" aria-hidden="true" />
                            Soil type
                          </>
                        </FieldLabel>
                        <Combobox
                          options={[...MONITOR_SOIL_TYPES]}
                          value={soilType}
                          onChange={(v) => {
                            setSoilType(v);
                            setErrors((p) => ({ ...p, soil_type: undefined }));
                          }}
                          placeholder="Select soil type"
                          searchPlaceholder="Search soil types…"
                        />
                      </Field>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    {NUMERIC_FIELDS.map(({ key, label, icon: Icon }) => (
                      <div key={key} data-field={key}>
                        <Field error={errors[key] ?? null}>
                          <FieldLabel>
                            <>
                              <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
                              {label}
                            </>
                          </FieldLabel>
                          <NumericInput
                            value={values[key]}
                            unit={MONITOR_RULES[key].unit}
                            step="any"
                            min={MONITOR_RULES[key].min}
                            max={MONITOR_RULES[key].max}
                            onChange={(e) => setValue(key, e.target.value)}
                            onBlur={() => {
                              setTouched((p) => ({ ...p, [key]: true }));
                              setErrors((p) => ({
                                ...p,
                                [key]: validateNumeric(values[key], MONITOR_RULES[key]),
                              }));
                            }}
                          />
                        </Field>
                      </div>
                    ))}
                  </div>

                  <Button
                    type="submit"
                    size="lg"
                    fullWidth
                    loading={status === 'loading'}
                    loadingText="Assessing your field…"
                  >
                    <Activity aria-hidden="true" />
                    Get application plan
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </div>

        <div ref={resultsRef} className={cn('scroll-mt-24 lg:col-span-7')}>
          {status === 'idle' && (
            <EmptyState
              icon={Activity}
              title="Your application plan will appear here"
              description="Enter the crop you're growing and your current field readings. TerraMind will recommend a fertiliser, dosage and timing, and flag pest pressure."
            />
          )}
          {status === 'loading' && <StagedLoader stages={STAGES} title="Assessing your field" />}
          {status === 'error' && (
            <ErrorState
              title={isOffline ? 'Cannot reach TerraMind' : 'Assessment failed'}
              message={error ?? 'Something went wrong.'}
              isOffline={isOffline}
              onRetry={
                lastPayload.current ? () => void run(lastPayload.current as MonitorRequest) : undefined
              }
            />
          )}
          {status === 'success' && data && <MonitorResults result={data} />}
        </div>
      </div>
    </>
  );
}
