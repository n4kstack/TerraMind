/**
 * Types mirrored from the FastAPI Pydantic schemas.
 *
 * Sources:
 *   backend/app/schemas/advisor.py    -> BeforeSowingRequest / BeforeSowingResponse
 *   backend/app/schemas/monitor.py    -> GrowthStageRequest / GrowthStageResponse
 *   backend/app/schemas/diagnosis.py  -> DiagnosisResponse
 *   backend/app/api/v1/graph_rag.py   -> QueryRequest (response is an untyped
 *                                        pipeline dict, so it is modelled
 *                                        defensively below)
 *
 * Optional markers are deliberate: several response fields have defaults on the
 * backend but are absent when a sub-pipeline degrades, so the UI must handle
 * their absence rather than rendering `undefined`.
 */

/* ------------------------------------------------------------------ Advisor */

/**
 * Mirrors backend/schemas/request_response.py (POST /predict), NOT the v1
 * advisor schema. Both endpoints exist; /predict is the one the application
 * uses and returns strictly more information (execution mode, sync status,
 * per-crop local adaptation, and the district yield trajectory series).
 *
 * Numerous fields are Optional[...] on the backend and genuinely arrive as null
 * when a district has no historical record, so they are nullable here and the
 * UI must render an explicit "not available" rather than a zero.
 */

export type ExecutionMode = 'central' | 'edge' | 'local_only';

export interface CropEntry {
  crop: string;
  base_confidence: number;
  /** Signed adjustment applied by the local adaptation layer. */
  local_adjustment: number;
  final_confidence: number;
}

export interface ConfidenceBand {
  lower: number | null;
  upper: number | null;
}

export interface AdvisorRequest {
  N: number;
  P: number;
  K: number;
  ph: number;
  temperature: number;
  humidity: number;
  rainfall: number;
  soil_type: string;
  state: string;
  district: string;
  season: string;
  area?: number | null;
  mode: ExecutionMode;
}

export interface CropRecommenderResult {
  top_3: CropEntry[];
  selected_crop: string;
  adaptation_factors?: string[];
}

export interface YieldPredictorResult {
  expected_yield: number | null;
  unit: string;
  confidence_band: ConfidenceBand;
  explanation?: string;
}

export interface AgriConditionResult {
  sunlight_hours: number | null;
  irrigation_type: string;
  irrigation_need: string;
  explanation?: string;
  district_prior_used?: boolean;
  district_irrigation_summary?: string;
  crop_irrigated_pct?: number | null;
}

export interface DistrictIntelligenceResult {
  district_crop_share_percent?: number | null;
  yield_trend?: string | null;
  top_competing_crops?: string[];
  best_historical_season?: string | null;
  ten_year_trajectory_summary?: string | null;
  /** Parallel arrays: years[i] pairs with yields[i]. Null when unavailable. */
  ten_year_trajectory_data?: { years: number[]; yields: number[] } | null;
  irrigation_infrastructure_summary?: string | null;
  irrigation_infrastructure_data?: Record<string, number> | null;
  crop_irrigated_area_percent?: number | null;
  notes?: string[];
}

export interface SyncStatus {
  edge_version: string;
  central_version: string;
  last_sync?: string | null;
  stale: boolean;
}

export interface AdvisorResponse {
  input_summary: Record<string, unknown>;
  execution_mode: string;
  model_version: string;
  adaptation_applied: boolean;
  sync_status: SyncStatus;
  crop_recommender: CropRecommenderResult;
  yield_predictor: YieldPredictorResult;
  agri_condition_advisor: AgriConditionResult;
  district_intelligence: DistrictIntelligenceResult;
  system_notes?: string[];
  latency_ms?: number;
}

/* ------------------------------------------------------------------ Monitor */

export interface MonitorRequest {
  temperature: number;
  humidity: number;
  moisture: number;
  soil_type: string;
  crop_type: string;
  N: number;
  P: number;
  K: number;
  ph: number;
  rainfall: number;
}

export interface MonitorResponse {
  recommended_fertilizer: string;
  pest_level: string;
  dosage: number;
  apply_after_days: number;
  expected_yield_after_dosage: number;
}

/* ---------------------------------------------------------------- Diagnosis */

export interface TopPrediction {
  crop: string;
  /** Serialised as `class` by the backend alias. */
  class: string;
  confidence: number;
}

export interface DiagnosisResponse {
  identified_crop: string;
  identified_class: string;
  confidence: number;
  top_k_predictions: TopPrediction[];
  assistant_available: boolean;
  report_id?: string | null;
}

/** Exactly the values backend/app/api/v1/diagnosis.py returns. */
export type ReportStatus = 'ready' | 'processing' | 'error' | 'not_found';

/**
 * The background LLM report is structured JSON, not prose: eleven named
 * sections that the PDF generator renders in a fixed order.
 * Every field is optional because a degraded generation can omit sections.
 */
export interface DiagnosisReportData {
  crop_identified?: string;
  disease_identified?: string;
  disease_overview?: string;
  symptoms?: string;
  causes?: string;
  severity?: string;
  immediate_steps?: string;
  treatment?: string;
  prevention?: string;
  possible_impact?: string;
  monitoring_advice?: string;
}

export interface DiagnosisReport {
  status: ReportStatus;
  data?: DiagnosisReportData;
  message?: string;
}

/* ---------------------------------------------------- Diagnosis assistant */

export interface AssistantRequest {
  question: string;
  top_k?: number;
  identified_crop?: string;
  identified_class?: string;
  report_id?: string;
}

export interface AssistantSource {
  [key: string]: unknown;
}

export interface AssistantResponse {
  answer: string;
  /** The backend refuses off-topic questions; `allowed:false` explains why. */
  allowed?: boolean;
  reason?: string;
  sources?: AssistantSource[];
}

/* ----------------------------------------------------------------- AugNosis */

/**
 * Verified against graph_rag/query_engine.py::QueryContext by calling the live
 * endpoint. The distinction below matters: `high_risk_*` are arrays of plain
 * id strings, but `soil_conflicts` and `tank_mix_warnings` are arrays of
 * OBJECTS. Rendering those directly as React children throws "Objects are not
 * valid as a React child" and destroys the answer, so each has a named type and
 * an explicit formatter in the UI.
 */
export interface SoilConflict {
  pesticide?: string;
  soil?: string;
  conflict_type?: string;
  severity?: string;
  reason?: string;
  recommendation?: string;
}

export interface TankMixWarning {
  pesticide_a?: string;
  pesticide_b?: string;
  reason?: string;
  severity?: string;
}

export interface AugNosisContext {
  crop?: string | null;
  /** Node id strings. */
  high_risk_pests_now?: string[];
  high_risk_diseases_now?: string[];
  /** Objects, not strings — see note above. */
  soil_conflicts?: SoilConflict[];
  tank_mix_warnings?: TankMixWarning[];
  /** Prose actions, already sentence-formatted by the backend. */
  urgent_actions?: string[];
  /** Knowledge-graph provenance, e.g. "ICAR recommendations". */
  data_sources?: string[];
  /** Retrieval confidence band: "high" | "medium" | "low". */
  confidence?: string;
  warnings?: string[];
  [key: string]: unknown;
}

export interface AugNosisResponse {
  query?: string;
  response: string;
  context?: AugNosisContext;
  parsed_intent?: Record<string, unknown>;
  kg_context_text?: string;
  engine?: Record<string, unknown>;
}

export interface AugNosisHealth {
  status: string;
  provider?: string;
  model?: string;
  kg_nodes?: number;
  detail?: string;
}

/* ------------------------------------------------------------------- Shared */

/**
 * Values are lowercase because that is exactly what the models were trained on
 * and what the previous form submitted. Display capitalisation happens in the
 * UI layer only -- capitalising these would silently change the payload.
 */
export const SOIL_TYPES = [
  'loamy',
  'sandy',
  'clay',
  'black',
  'red',
  'alluvial',
  'laterite',
  'chalky',
  'peaty',
  'saline',
] as const;

export const SEASONS = ['kharif', 'rabi', 'summer', 'winter', 'whole year', 'autumn'] as const;

export type SoilType = (typeof SOIL_TYPES)[number];
export type Season = (typeof SEASONS)[number];

/**
 * Monitor vocabularies, taken verbatim from the categorical columns of
 * TerraMind_Datasets/fertilizer_giant_training_dataset.csv. These are
 * capitalised where the advisor's are lowercase because that is how each model
 * was trained; the encoder will not recognise a different casing.
 */
export const MONITOR_CROP_TYPES = [
  'Cotton',
  'Groundnut',
  'Maize',
  'Pulses',
  'Rice',
  'Soybean',
  'Sugarcane',
  'Tomato',
  'Wheat',
] as const;

export const MONITOR_SOIL_TYPES = ['Black', 'Clayey', 'Loamy', 'Red', 'Sandy'] as const;
