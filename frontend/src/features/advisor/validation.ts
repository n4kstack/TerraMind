/**
 * Field validation for agronomic inputs.
 *
 * Ranges are physical/agronomic plausibility bounds, not model constraints:
 * the point is to catch a mistyped "800" for pH before it becomes a confident
 * but meaningless recommendation. Bounds are deliberately generous — rejecting
 * a real but unusual reading would be worse than accepting it.
 */

export interface NumericRule {
  min: number;
  max: number;
  label: string;
  unit?: string;
}

/**
 * Errors are keyed by field name and may be explicitly null (checked, valid)
 * or absent (not yet checked). Both must be representable, hence the union.
 */
export type FieldErrors = Record<string, string | null | undefined>;

export type AdvisorNumericKey =
  | 'N'
  | 'P'
  | 'K'
  | 'ph'
  | 'temperature'
  | 'humidity'
  | 'rainfall'
  | 'area';

export type MonitorNumericKey =
  | 'temperature'
  | 'humidity'
  | 'moisture'
  | 'N'
  | 'P'
  | 'K'
  | 'ph'
  | 'rainfall';

/**
 * Explicitly annotated rather than `as const satisfies`: const-narrowing gave
 * each entry its own literal type, so `unit` was absent from the pH rule's type
 * and any generic `RULES[key].unit` access failed to compile.
 */
export const ADVISOR_RULES: Record<AdvisorNumericKey, NumericRule> = {
  N: { min: 0, max: 300, label: 'Nitrogen', unit: 'kg/ha' },
  P: { min: 0, max: 300, label: 'Phosphorus', unit: 'kg/ha' },
  K: { min: 0, max: 300, label: 'Potassium', unit: 'kg/ha' },
  ph: { min: 0, max: 14, label: 'Soil pH' },
  temperature: { min: -10, max: 60, label: 'Temperature', unit: '°C' },
  humidity: { min: 0, max: 100, label: 'Humidity', unit: '%' },
  rainfall: { min: 0, max: 5000, label: 'Rainfall', unit: 'mm' },
  area: { min: 0.01, max: 100000, label: 'Area', unit: 'ha' },
};

/**
 * Monitor units differ from Advisor: the fertilizer dataset records NPK in ppm,
 * not kg/ha (see TerraMind_Datasets/fertilizer_giant_training_dataset.csv
 * headers). Labelling these kg/ha would invite readings on the wrong scale.
 */
export const MONITOR_RULES: Record<MonitorNumericKey, NumericRule> = {
  temperature: { min: -10, max: 60, label: 'Temperature', unit: '°C' },
  humidity: { min: 0, max: 100, label: 'Humidity', unit: '%' },
  moisture: { min: 0, max: 100, label: 'Soil moisture', unit: '%' },
  N: { min: 0, max: 500, label: 'Nitrogen', unit: 'ppm' },
  P: { min: 0, max: 500, label: 'Phosphorus', unit: 'ppm' },
  K: { min: 0, max: 500, label: 'Potassium', unit: 'ppm' },
  ph: { min: 0, max: 14, label: 'Soil pH' },
  rainfall: { min: 0, max: 5000, label: 'Rainfall', unit: 'mm' },
};

/** Returns an error message, or null when the value is acceptable. */
export function validateNumeric(
  raw: string,
  rule: NumericRule,
  { required = true }: { required?: boolean } = {},
): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return required ? `${rule.label} is required` : null;

  const value = Number(trimmed);
  if (Number.isNaN(value)) return `${rule.label} must be a number`;
  if (value < rule.min || value > rule.max) {
    const unit = rule.unit ? ` ${rule.unit}` : '';
    return `${rule.label} should be between ${rule.min} and ${rule.max}${unit}`;
  }
  return null;
}
