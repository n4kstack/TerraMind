import stateDistrictMapping from '@/data/state_district_mapping.json';
import { API_BASE_URL, AUGNOSIS_TIMEOUT_MS, INFERENCE_TIMEOUT_MS, postJson, request } from './client';
import type {
  AdvisorRequest,
  AdvisorResponse,
  AssistantRequest,
  AssistantResponse,
  AugNosisHealth,
  AugNosisResponse,
  DiagnosisReport,
  DiagnosisResponse,
  MonitorRequest,
  MonitorResponse,
} from './types';

export * from './types';
export { ApiError, API_BASE_URL, API_V1_BASE_URL } from './client';

const districtMap = stateDistrictMapping as Record<string, string[]>;

/* ---------------------------------------------------------------- Geography */

/**
 * States and districts live at the API root, not under /api/v1, and the bundled
 * JSON is a genuine offline fallback rather than a mock: it is the same dataset
 * the backend serves. Falling back keeps the form usable when the backend is
 * cold, which is common on free-tier hosting.
 */
export async function fetchStates(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/states`);
    if (res.ok) {
      const data = (await res.json()) as { states?: string[] };
      if (data.states?.length) return data.states;
    }
  } catch {
    // Fall through to the bundled map.
  }
  return Object.keys(districtMap).sort();
}

export async function fetchDistricts(state: string): Promise<string[]> {
  if (!state) return [];
  try {
    const res = await fetch(`${API_BASE_URL}/api/districts/${encodeURIComponent(state)}`);
    if (res.ok) {
      const data = (await res.json()) as { districts?: string[] };
      if (data.districts?.length) return data.districts;
    }
  } catch {
    // Fall through to the bundled map.
  }
  return districtMap[state] ?? [];
}

/* ------------------------------------------------------------------ Advisor */

/** Mounted at the application root, not under /api/v1. */
export function predictAdvisor(payload: AdvisorRequest): Promise<AdvisorResponse> {
  return postJson<AdvisorResponse>('/predict', payload, {
    timeoutMs: INFERENCE_TIMEOUT_MS,
    base: 'root',
  });
}

/* ------------------------------------------------------------------ Monitor */

export function predictMonitor(payload: MonitorRequest): Promise<MonitorResponse> {
  return postJson<MonitorResponse>('/monitor/predict', payload, {
    timeoutMs: INFERENCE_TIMEOUT_MS,
  });
}

/* ---------------------------------------------------------------- Diagnosis */

export function predictDiagnosis(file: File, topK = 3): Promise<DiagnosisResponse> {
  const formData = new FormData();
  formData.append('file', file);
  // Content-Type is intentionally unset: the browser must add the multipart
  // boundary itself, and setting it manually breaks the upload.
  return request<DiagnosisResponse>(`/diagnosis/predict?top_k=${topK}`, {
    method: 'POST',
    body: formData,
    timeoutMs: INFERENCE_TIMEOUT_MS,
  });
}

export function fetchDiagnosisReport(reportId: string): Promise<DiagnosisReport> {
  return request<DiagnosisReport>(`/diagnosis/report/${reportId}`).catch((error) => {
    // A 404 here means "not generated yet", which is an expected polling state
    // rather than a failure worth surfacing to the user.
    if (error && typeof error === 'object' && 'status' in error && error.status === 404) {
      return { status: 'not_found' } as DiagnosisReport;
    }
    throw error;
  });
}

export function markReportDownloaded(reportId: string): Promise<unknown> {
  return request(`/diagnosis/report/${reportId}/download`, { method: 'POST' });
}

/**
 * Follow-up assistant, scoped to a completed diagnosis. The backend gates
 * answers on the report having been generated, hence the report_id.
 */
export function askDiagnosisAssistant(payload: AssistantRequest): Promise<AssistantResponse> {
  return postJson<AssistantResponse>('/chatbot/ask', payload, {
    timeoutMs: INFERENCE_TIMEOUT_MS,
  });
}

/* ----------------------------------------------------------------- AugNosis */

export function queryAugNosis(query: string, useLlm = true): Promise<AugNosisResponse> {
  return postJson<AugNosisResponse>(
    '/graph-rag/query',
    { query, use_llm: useLlm },
    { timeoutMs: AUGNOSIS_TIMEOUT_MS },
  );
}

export function fetchAugNosisHealth(): Promise<AugNosisHealth> {
  return request<AugNosisHealth>('/graph-rag/health', { timeoutMs: 10_000 });
}
