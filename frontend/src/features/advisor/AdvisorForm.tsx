import { useEffect, useMemo, useState } from 'react';
import { Droplets, FlaskConical, Layers, MapPin, Sprout, Thermometer, Wheat, Wind } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Combobox } from '@/components/ui/Combobox';
import { Field, FieldLabel, NumericInput } from '@/components/ui/Field';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { fetchDistricts, fetchStates, SEASONS, SOIL_TYPES } from '@/lib/api';
import type { AdvisorRequest, ExecutionMode } from '@/lib/api';
import { humanize } from '@/lib/utils';
import { ADVISOR_RULES, validateNumeric, type FieldErrors } from './validation';

type NumericKey = 'N' | 'P' | 'K' | 'ph' | 'temperature' | 'humidity' | 'rainfall' | 'area';

/** Defaults carried over from the previous form so behaviour is unchanged. */
const INITIAL: Record<NumericKey, string> = {
  N: '90',
  P: '42',
  K: '43',
  ph: '6.5',
  temperature: '25',
  humidity: '80',
  rainfall: '200',
  area: '',
};

const MODES: { value: ExecutionMode; label: string; hint: string }[] = [
  { value: 'central', label: 'Central', hint: 'Full-power models on the server' },
  { value: 'edge', label: 'Edge', hint: 'Compressed models, optimised for low connectivity' },
  { value: 'local_only', label: 'Local', hint: 'On-device adaptation only' },
];

function SectionHeading({ icon: Icon, children }: { icon: typeof Sprout; children: string }) {
  return (
    <h2 className="mb-3 flex items-center gap-2 text-label uppercase tracking-wider text-muted-foreground">
      <Icon className="size-3.5 text-primary" aria-hidden="true" />
      {children}
    </h2>
  );
}

export function AdvisorForm({
  onSubmit,
  loading,
}: {
  onSubmit: (payload: AdvisorRequest) => void;
  loading: boolean;
}) {
  const [values, setValues] = useState<Record<NumericKey, string>>(INITIAL);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const [soilType, setSoilType] = useState<string>('loamy');
  const [season, setSeason] = useState<string>('kharif');
  const [mode, setMode] = useState<ExecutionMode>('central');

  const [states, setStates] = useState<string[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);
  const [state, setState] = useState<string | null>(null);
  const [district, setDistrict] = useState<string | null>(null);
  const [loadingStates, setLoadingStates] = useState(true);
  const [loadingDistricts, setLoadingDistricts] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchStates()
      .then((result) => {
        if (!cancelled) setStates(result);
      })
      .finally(() => {
        if (!cancelled) setLoadingStates(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!state) {
      setDistricts([]);
      return;
    }
    let cancelled = false;
    setLoadingDistricts(true);
    // Clearing the district here is essential: keeping a district from the
    // previous state would submit an impossible state/district pair.
    setDistrict(null);
    fetchDistricts(state)
      .then((result) => {
        if (!cancelled) setDistricts(result);
      })
      .finally(() => {
        if (!cancelled) setLoadingDistricts(false);
      });
    return () => {
      cancelled = true;
    };
  }, [state]);

  function setValue(key: NumericKey, raw: string) {
    setValues((prev) => ({ ...prev, [key]: raw }));
    // Re-validate on change only after the field has been blurred once, so the
    // user isn't shouted at mid-typing.
    if (touched[key]) {
      setErrors((prev) => ({
        ...prev,
        [key]: validateNumeric(raw, ADVISOR_RULES[key], { required: key !== 'area' }),
      }));
    }
  }

  function handleBlur(key: NumericKey) {
    setTouched((prev) => ({ ...prev, [key]: true }));
    setErrors((prev) => ({
      ...prev,
      [key]: validateNumeric(values[key], ADVISOR_RULES[key], { required: key !== 'area' }),
    }));
  }

  const soilOptions = useMemo(() => SOIL_TYPES.map(humanize), []);
  const seasonOptions = useMemo(() => SEASONS.map(humanize), []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const nextErrors: Record<string, string | null> = {};
    (Object.keys(ADVISOR_RULES) as NumericKey[]).forEach((key) => {
      nextErrors[key] = validateNumeric(values[key], ADVISOR_RULES[key], {
        required: key !== 'area',
      });
    });
    if (!state) nextErrors.state = 'Select a state';
    if (!district) nextErrors.district = 'Select a district';

    const cleaned = Object.fromEntries(
      Object.entries(nextErrors).filter(([, v]) => v),
    ) as Record<string, string>;

    setErrors(cleaned);
    setTouched(
      Object.fromEntries((Object.keys(ADVISOR_RULES) as string[]).map((k) => [k, true])),
    );

    if (Object.keys(cleaned).length > 0) {
      // Move focus to the first problem so keyboard and screen-reader users
      // are taken to it rather than left guessing.
      const firstKey = Object.keys(cleaned)[0];
      document
        .querySelector<HTMLElement>(`[data-field="${firstKey}"] input, [data-field="${firstKey}"] button`)
        ?.focus();
      return;
    }

    onSubmit({
      N: Number(values.N),
      P: Number(values.P),
      K: Number(values.K),
      ph: Number(values.ph),
      temperature: Number(values.temperature),
      humidity: Number(values.humidity),
      rainfall: Number(values.rainfall),
      soil_type: soilType,
      season,
      state: state as string,
      district: district as string,
      area: values.area.trim() ? Number(values.area) : null,
      mode,
    });
  }

  const numericField = (key: NumericKey, Icon: typeof Sprout, label: string) => {
    const rule = ADVISOR_RULES[key];
    return (
      <div data-field={key}>
        <Field error={errors[key] ?? null}>
          <FieldLabel optional={key === 'area'}>
            <>
              <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
              {label}
            </>
          </FieldLabel>
          <NumericInput
            value={values[key]}
            unit={rule.unit}
            step="any"
            min={rule.min}
            max={rule.max}
            placeholder={key === 'area' ? 'e.g. 2.5' : undefined}
            onChange={(e) => setValue(key, e.target.value)}
            onBlur={() => handleBlur(key)}
          />
        </Field>
      </div>
    );
  };

  return (
    <Card elevated>
      <CardContent className="pt-5 sm:pt-6">
        <form onSubmit={handleSubmit} noValidate className="space-y-7">
          <section>
            <SectionHeading icon={Layers}>Inference mode</SectionHeading>
            <SegmentedControl
              label="Inference mode"
              options={MODES}
              value={mode}
              onChange={setMode}
            />
            <p className="mt-2 text-xs text-muted-foreground">
              {MODES.find((m) => m.value === mode)?.hint}
            </p>
          </section>

          <section>
            <SectionHeading icon={FlaskConical}>Soil nutrients</SectionHeading>
            <div className="grid grid-cols-2 gap-3">
              {numericField('N', FlaskConical, 'Nitrogen')}
              {numericField('P', FlaskConical, 'Phosphorus')}
              {numericField('K', FlaskConical, 'Potassium')}
              {numericField('ph', FlaskConical, 'Soil pH')}
            </div>
          </section>

          <section>
            <SectionHeading icon={Thermometer}>Climate</SectionHeading>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {numericField('temperature', Thermometer, 'Temperature')}
              {numericField('humidity', Wind, 'Humidity')}
              {numericField('rainfall', Droplets, 'Rainfall')}
            </div>
          </section>

          <section>
            <SectionHeading icon={MapPin}>Field</SectionHeading>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div data-field="soil_type">
                <Field>
                  <FieldLabel>
                    <>
                      <Layers className="size-3.5 text-muted-foreground" aria-hidden="true" />
                      Soil type
                    </>
                  </FieldLabel>
                  <Combobox
                    options={soilOptions}
                    value={humanize(soilType)}
                    onChange={(v) => setSoilType(v.toLowerCase())}
                    placeholder="Select soil type"
                    searchPlaceholder="Search soil types…"
                  />
                </Field>
              </div>

              <div data-field="season">
                <Field>
                  <FieldLabel>
                    <>
                      <Wheat className="size-3.5 text-muted-foreground" aria-hidden="true" />
                      Season
                    </>
                  </FieldLabel>
                  <Combobox
                    options={seasonOptions}
                    value={humanize(season)}
                    onChange={(v) => setSeason(v.toLowerCase())}
                    placeholder="Select season"
                    searchPlaceholder="Search seasons…"
                  />
                </Field>
              </div>

              <div data-field="state">
                <Field error={errors.state ?? null}>
                  <FieldLabel>
                    <>
                      <MapPin className="size-3.5 text-muted-foreground" aria-hidden="true" />
                      State
                    </>
                  </FieldLabel>
                  <Combobox
                    options={states}
                    value={state}
                    onChange={(v) => {
                      setState(v);
                      setErrors((prev) => ({ ...prev, state: undefined }));
                    }}
                    placeholder="Select state"
                    searchPlaceholder="Search states…"
                    formatLabel={humanize}
                    loading={loadingStates}
                  />
                </Field>
              </div>

              <div data-field="district">
                <Field
                  error={errors.district ?? null}
                  description={!state ? 'Choose a state first' : undefined}
                >
                  <FieldLabel>
                    <>
                      <MapPin className="size-3.5 text-muted-foreground" aria-hidden="true" />
                      District
                    </>
                  </FieldLabel>
                  <Combobox
                    options={districts}
                    value={district}
                    onChange={(v) => {
                      setDistrict(v);
                      setErrors((prev) => ({ ...prev, district: undefined }));
                    }}
                    placeholder={state ? 'Select district' : 'Select a state first'}
                    searchPlaceholder="Search districts…"
                    formatLabel={humanize}
                    disabled={!state}
                    loading={loadingDistricts}
                  />
                </Field>
              </div>

              <div className="sm:col-span-2">{numericField('area', Sprout, 'Area')}</div>
            </div>
          </section>

          <Button type="submit" size="lg" fullWidth loading={loading} loadingText="Analysing your field…">
            <Sprout aria-hidden="true" />
            Get recommendation
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
