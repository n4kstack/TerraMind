/// <reference types="vite/client" />

/**
 * Supplies types for `import.meta.env` and for side-effect imports of CSS and
 * static assets. Without this reference, strict TypeScript rejects both.
 */

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_MONITOR_TIMEOUT_MS?: string;
  readonly VITE_DIAGNOSIS_DEFAULT_TOP_K?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
