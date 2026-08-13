/**
 * Shared fetch client.
 *
 * Centralises three things the per-service modules each used to reimplement
 * slightly differently: timeouts, FastAPI error-envelope unwrapping, and
 * distinguishing "the network is gone" from "the server said no". That
 * distinction matters here because the audience is frequently on poor rural
 * connectivity, and "check your connection" is actionable while
 * "Server error: 500" is not.
 */

const rawBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';
export const API_BASE_URL = rawBase.replace(/\/+$/, '');
export const API_V1_BASE_URL = `${API_BASE_URL}/api/v1`;

export const DEFAULT_TIMEOUT_MS = Number(import.meta.env.VITE_MONITOR_TIMEOUT_MS) || 30_000;
/** Inference on cold containers is slow; give the heavy endpoints more room. */
export const INFERENCE_TIMEOUT_MS = 90_000;
/**
 * AugNosis traverses the knowledge graph and then calls a hosted LLM. A measured
 * round trip against the live backend took 70s, which left almost no headroom
 * under the 90s inference budget — a slightly slower generation would abort a
 * request that was about to succeed.
 */
export const AUGNOSIS_TIMEOUT_MS = 180_000;

export class ApiError extends Error {
  readonly status: number;
  readonly isOffline: boolean;
  readonly isTimeout: boolean;
  /**
   * The caller aborted deliberately. Distinct from `isTimeout` even though both
   * surface as an `AbortError`: a timeout is a failure worth reporting, whereas
   * a cancellation is the user getting what they asked for and must never be
   * presented as an error.
   */
  readonly isCanceled: boolean;

  constructor(
    message: string,
    opts: { status?: number; isOffline?: boolean; isTimeout?: boolean; isCanceled?: boolean } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = opts.status ?? 0;
    this.isOffline = opts.isOffline ?? false;
    this.isTimeout = opts.isTimeout ?? false;
    this.isCanceled = opts.isCanceled ?? false;
  }
}

/** FastAPI returns `detail` as a string, or an array of validation objects. */
function extractDetail(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => (typeof d === 'object' && d && 'msg' in d ? String((d as { msg: unknown }).msg) : null))
      .filter(Boolean);
    if (messages.length) return messages.join('. ');
  }
  return fallback;
}

interface RequestOptions extends Omit<RequestInit, 'signal'> {
  timeoutMs?: number;
  /**
   * Which prefix to resolve `path` against. The unified v1 suite lives under
   * /api/v1, but the edge advisor (`/predict`, `/metadata`, `/sync/*`) is
   * mounted at the application root.
   */
  base?: 'v1' | 'root';
  /**
   * Caller-owned cancellation, linked to (not replacing) the internal timeout
   * controller. Long generative endpoints can run for minutes, and a user who
   * has changed their mind should not have to wait out a request whose answer
   * they no longer want.
   */
  signal?: AbortSignal;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, base = 'v1', signal: callerSignal, ...init } = options;
  const prefix = base === 'root' ? API_BASE_URL : API_V1_BASE_URL;

  if (callerSignal?.aborted) {
    throw new ApiError('Request canceled.', { isCanceled: true });
  }

  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    throw new ApiError('You appear to be offline. Check your connection and try again.', {
      isOffline: true,
    });
  }

  const controller = new AbortController();
  // fetch reports both causes as a bare AbortError, so record which fired.
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const onCallerAbort = () => controller.abort();
  callerSignal?.addEventListener('abort', onCallerAbort, { once: true });

  try {
    const response = await fetch(`${prefix}${path}`, { ...init, signal: controller.signal });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(extractDetail(body, `Request failed (${response.status})`), {
        status: response.status,
      });
    }

    // 204 and empty bodies are valid for the mark-downloaded endpoint.
    const text = await response.text();
    return (text ? JSON.parse(text) : null) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      // Cancellation wins over the timeout: if the user aborted, that is the
      // truthful cause even in the rare case both fire in the same tick.
      if (callerSignal?.aborted) {
        throw new ApiError('Request canceled.', { isCanceled: true });
      }
      if (timedOut) {
        throw new ApiError(
          `The request took longer than ${Math.round(timeoutMs / 1000)}s. The model may be starting up — please retry.`,
          { isTimeout: true },
        );
      }
    }
    // A bare TypeError from fetch means the request never reached the server.
    throw new ApiError('Could not reach the TerraMind server. Check your connection and try again.', {
      isOffline: true,
    });
  } finally {
    clearTimeout(timer);
    callerSignal?.removeEventListener('abort', onCallerAbort);
  }
}

export function postJson<T>(
  path: string,
  body: unknown,
  opts: { timeoutMs?: number; base?: 'v1' | 'root'; signal?: AbortSignal } = {},
): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    ...opts,
  });
}
