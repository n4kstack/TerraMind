import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  GitBranch,
  RefreshCw,
  Layers,
  Link2,
  FileCode2,
  Package,
  Workflow,
  Plus,
  Minus,
} from 'lucide-react';
import { architectureService } from '../services/architectureService';
import ArchitectureDiagram from '../components/architecture/ArchitectureDiagram';

const AUTO_REFRESH_MS = 10000;
const LAYER_COLORS = {
  ui: '#38bdf8',
  business: '#22c55e',
  data: '#f59e0b',
  external: '#94a3b8',
};

const EXECUTION_GUIDES = [
  {
    id: 'advisor',
    title: 'Advisor Execution',
    steps: [
      'User submits NPK + climate + location in PredictionForm.',
      'Frontend services call /api/v1/advisor and prediction endpoints.',
      'Backend advisor pipeline runs mode-aware logic (Edge/Central/Local).',
      'Model outputs and district intelligence return to ResultsDashboard.',
    ],
  },
  {
    id: 'monitor',
    title: 'Monitor Execution',
    steps: [
      'Growth metrics are captured from the monitor form.',
      'Frontend monitor service sends feature vectors to monitor API.',
      'Growth-stage model infers health/risk and recommendation signals.',
      'UI renders stage advisories and action summaries.',
    ],
  },
  {
    id: 'diagnosis',
    title: 'Diagnosis + AugNosis Execution',
    steps: [
      'Image upload triggers diagnosis predict endpoint.',
      'CNN model identifies crop/disease and schedules report generation.',
      'AugNosis/Graph retrieval + Gemini/LLM synthesize expert context.',
      'Report status polling resolves to downloadable recommendations.',
    ],
  },
];

function collectPathsByAny(snapshot, tokens) {
  if (!snapshot?.nodes?.length) return [];
  const hits = snapshot.nodes
    .filter((node) => String(node.id || '').startsWith('file::'))
    .filter((node) => {
      const path = String(node.path || '');
      return tokens.some((token) => path.includes(token));
    })
    .map((node) => node.path);

  return [...new Set(hits)].sort();
}

function buildOverviewGraph(snapshot) {
  if (!snapshot?.nodes?.length) {
    return {
      generated_at: null,
      summary: { files_scanned: 0, nodes: 0, edges: 0, layers: 4 },
      layers: [
        { id: 'ui', label: 'UI Layer', color: LAYER_COLORS.ui },
        { id: 'business', label: 'Business Logic Layer', color: LAYER_COLORS.business },
        { id: 'data', label: 'Data / Model Layer', color: LAYER_COLORS.data },
        { id: 'external', label: 'External Services', color: LAYER_COLORS.external },
      ],
      nodes: [],
      edges: [],
    };
  }

  const makeNode = ({ id, label, layer, role, tokens = [], path = id, exports = [] }) => {
    const modules = collectPathsByAny(snapshot, tokens);
    return {
      id,
      label,
      path,
      role,
      layer,
      color: LAYER_COLORS[layer],
      exports,
      dependencies: modules,
      metadata: {
        module_count: modules.length,
      },
    };
  };

  const nodes = [
    makeNode({
      id: 'overview::ui_shell',
      label: 'Frontend Shell',
      layer: 'ui',
      role: 'routing_and_layout',
      tokens: ['frontend/src/App.jsx', 'frontend/src/components/Layout.jsx', 'frontend/src/components/Navbar.jsx'],
      exports: ['Routes', 'Top Navigation', 'Page Layout'],
    }),
    makeNode({
      id: 'overview::ui_advisor',
      label: 'Advisor UI',
      layer: 'ui',
      role: 'user_workflow',
      tokens: ['frontend/src/pages/Advisor.jsx', 'frontend/src/components/PredictionForm.jsx', 'frontend/src/components/ResultsDashboard.jsx'],
      exports: ['Input capture', 'Recommendation display'],
    }),
    makeNode({
      id: 'overview::ui_monitor',
      label: 'Monitor UI',
      layer: 'ui',
      role: 'user_workflow',
      tokens: ['frontend/src/pages/Monitor.jsx', 'frontend/src/components/forms/GrowthStageForm.jsx'],
      exports: ['Stage metrics', 'Monitoring output'],
    }),
    makeNode({
      id: 'overview::ui_diagnosis',
      label: 'Diagnosis UI',
      layer: 'ui',
      role: 'user_workflow',
      tokens: ['frontend/src/pages/Diagnosis.jsx', 'frontend/src/components/forms/ImageUploadForm.jsx', 'frontend/src/components/results/DiagnosisResultCard.jsx'],
      exports: ['Image diagnosis', 'Report polling'],
    }),
    makeNode({
      id: 'overview::ui_augnosis',
      label: 'AugNosis UI',
      layer: 'ui',
      role: 'user_workflow',
      tokens: ['frontend/src/pages/GraphRAG.jsx', 'frontend/src/components/GraphRAGChat.jsx'],
      exports: ['Knowledge graph Q&A', 'LLM response UI'],
    }),
    makeNode({
      id: 'overview::frontend_services',
      label: 'Frontend Service Layer',
      layer: 'business',
      role: 'api_orchestration',
      tokens: ['frontend/src/services/'],
      exports: ['API wrappers', 'Request/error handling'],
    }),
    makeNode({
      id: 'overview::api_gateway',
      label: 'FastAPI Gateway',
      layer: 'business',
      role: 'routing_and_boundary',
      tokens: ['backend/app/main.py', 'backend/app/api/v1/'],
      exports: ['REST endpoints', 'CORS + boundary management'],
    }),
    makeNode({
      id: 'overview::advisor_engine',
      label: 'Advisor Engine',
      layer: 'business',
      role: 'domain_orchestrator',
      tokens: ['backend/app/api/v1/advisor.py', 'backend/app/services/pre_sowing_pipeline.py', 'backend/services/benchmark_service.py'],
      exports: ['Crop recommendation', 'Yield + district context'],
    }),
    makeNode({
      id: 'overview::monitor_engine',
      label: 'Monitor Engine',
      layer: 'business',
      role: 'domain_orchestrator',
      tokens: ['backend/app/api/v1/monitor.py', 'backend/app/services/growth_stage_service.py'],
      exports: ['Growth diagnostics', 'Action advisories'],
    }),
    makeNode({
      id: 'overview::diagnosis_engine',
      label: 'Diagnosis Engine',
      layer: 'business',
      role: 'domain_orchestrator',
      tokens: ['backend/app/api/v1/diagnosis.py', 'backend/app/services/diagnosis_service.py', 'ml/post_symptom_diagnosis/'],
      exports: ['Crop+disease inference', 'Async report generation'],
    }),
    makeNode({
      id: 'overview::augnosis_engine',
      label: 'AugNosis Engine',
      layer: 'business',
      role: 'rag_orchestrator',
      tokens: ['backend/app/api/v1/graph_rag.py', 'backend/app/api/v1/chatbot.py', 'graph_rag/', 'backend/app/chatbot/'],
      exports: ['Graph retrieval', 'Expert response synthesis'],
    }),
    makeNode({
      id: 'overview::model_layer',
      label: 'ML Model Layer',
      layer: 'data',
      role: 'prediction_models',
      tokens: ['backend/models/', 'models/', 'ml/'],
      exports: ['Training + inference pipelines'],
    }),
    makeNode({
      id: 'overview::artifact_layer',
      label: 'Artifacts & Schemas',
      layer: 'data',
      role: 'model_artifacts_and_contracts',
      tokens: ['backend/artifacts/', 'trained_artifacts_fast/', 'backend/app/schemas/', 'schemas/'],
      exports: ['Model binaries', 'API contracts'],
    }),
    makeNode({
      id: 'overview::graph_data_layer',
      label: 'Knowledge Graph Data',
      layer: 'data',
      role: 'graph_and_retrieval_data',
      tokens: ['graph_rag/', 'graph rag source/', 'backend/app/chatbot/storage/'],
      exports: ['Graph nodes/edges', 'retrieval context'],
    }),
    {
      id: 'overview::external_llm',
      label: 'Gemini Runtime',
      path: 'external::llm',
      role: 'external_service',
      layer: 'external',
      color: LAYER_COLORS.external,
      exports: ['Managed LLM inference'],
      dependencies: [],
      metadata: {},
    },
    {
      id: 'overview::external_sources',
      label: 'External Sources',
      path: 'external::sources',
      role: 'external_service',
      layer: 'external',
      color: LAYER_COLORS.external,
      exports: ['AGRIS/AGRICOLA and external data'],
      dependencies: [],
      metadata: {},
    },
    {
      id: 'overview::mode_edge',
      label: 'Edge Path',
      path: 'mode::edge',
      role: 'execution_mode',
      layer: 'business',
      color: LAYER_COLORS.business,
      exports: ['Low-latency path'],
      dependencies: [],
      metadata: {},
    },
    {
      id: 'overview::mode_central',
      label: 'Central Path',
      path: 'mode::central',
      role: 'execution_mode',
      layer: 'business',
      color: LAYER_COLORS.business,
      exports: ['Full-capacity path'],
      dependencies: [],
      metadata: {},
    },
    {
      id: 'overview::mode_local',
      label: 'Local Path',
      path: 'mode::local',
      role: 'execution_mode',
      layer: 'business',
      color: LAYER_COLORS.business,
      exports: ['Local-only fallback'],
      dependencies: [],
      metadata: {},
    },
  ];

  const edgeDefs = [
    ['overview::ui_shell', 'overview::ui_advisor', 'navigation'],
    ['overview::ui_shell', 'overview::ui_monitor', 'navigation'],
    ['overview::ui_shell', 'overview::ui_diagnosis', 'navigation'],
    ['overview::ui_shell', 'overview::ui_augnosis', 'navigation'],

    ['overview::ui_advisor', 'overview::frontend_services', 'state/events'],
    ['overview::ui_monitor', 'overview::frontend_services', 'state/events'],
    ['overview::ui_diagnosis', 'overview::frontend_services', 'state/events'],
    ['overview::ui_augnosis', 'overview::frontend_services', 'state/events'],

    ['overview::frontend_services', 'overview::api_gateway', 'http api'],

    ['overview::api_gateway', 'overview::advisor_engine', 'advisor routes'],
    ['overview::api_gateway', 'overview::monitor_engine', 'monitor routes'],
    ['overview::api_gateway', 'overview::diagnosis_engine', 'diagnosis routes'],
    ['overview::api_gateway', 'overview::augnosis_engine', 'graph/chat routes'],

    ['overview::advisor_engine', 'overview::model_layer', 'predict'],
    ['overview::advisor_engine', 'overview::artifact_layer', 'load artifacts'],
    ['overview::monitor_engine', 'overview::model_layer', 'infer stage'],
    ['overview::diagnosis_engine', 'overview::model_layer', 'cnn infer'],
    ['overview::diagnosis_engine', 'overview::augnosis_engine', 'report context'],
    ['overview::augnosis_engine', 'overview::graph_data_layer', 'retrieve context'],
    ['overview::augnosis_engine', 'overview::external_llm', 'llm synth'],
    ['overview::augnosis_engine', 'overview::external_sources', 'external enrich'],

    ['overview::mode_edge', 'overview::advisor_engine', 'edge execution'],
    ['overview::mode_central', 'overview::advisor_engine', 'central execution'],
    ['overview::mode_local', 'overview::advisor_engine', 'local execution'],
  ];

  const edges = edgeDefs
    .filter(([source, target]) => nodes.some((node) => node.id === source) && nodes.some((node) => node.id === target))
    .map(([source, target, label], idx) => ({
      id: `overview-edge-${idx + 1}`,
      source,
      target,
      type: 'flow',
      label,
    }));

  return {
    generated_at: snapshot.generated_at,
    summary: {
      files_scanned: snapshot.summary?.files_scanned ?? 0,
      nodes: nodes.length,
      edges: edges.length,
      layers: 4,
    },
    layers: [
      { id: 'ui', label: 'UI Layer', color: LAYER_COLORS.ui },
      { id: 'business', label: 'Business Logic Layer', color: LAYER_COLORS.business },
      { id: 'data', label: 'Data / Model Layer', color: LAYER_COLORS.data },
      { id: 'external', label: 'External Services', color: LAYER_COLORS.external },
    ],
    nodes,
    edges,
  };
}

function formatTimeLabel(dateObj) {
  if (!dateObj) return 'N/A';
  return dateObj.toLocaleTimeString();
}

export default function Architecture() {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [zoomPercent, setZoomPercent] = useState(100);
  const [selectedNodeId, setSelectedNodeId] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);

  const svgRef = useRef(null);
  const fingerprintRef = useRef(null);
  const loadingRef = useRef(false);

  const loadSnapshot = useCallback(async (force = false, silent = false) => {
    if (loadingRef.current) return;
    loadingRef.current = true;

    if (!silent) {
      if (!snapshot) setLoading(true);
      setRefreshing(true);
    }

    try {
      const data = await architectureService.getSnapshot(force);
      const hasChanged = fingerprintRef.current !== data.fingerprint;

      if (hasChanged || !snapshot) {
        setSnapshot(data);
      }

      fingerprintRef.current = data.fingerprint;
      setLastUpdated(new Date());
      setError('');
    } catch (err) {
      setError(err.message || 'Unable to load architecture snapshot.');
    } finally {
      loadingRef.current = false;
      setLoading(false);
      setRefreshing(false);
    }
  }, [snapshot]);

  useEffect(() => {
    loadSnapshot(true, false);
  }, [loadSnapshot]);

  useEffect(() => {
    const timer = setInterval(() => {
      loadSnapshot(false, true);
    }, AUTO_REFRESH_MS);

    return () => clearInterval(timer);
  }, [loadSnapshot]);

  const graphData = useMemo(() => {
    if (!snapshot) return null;
    return buildOverviewGraph(snapshot);
  }, [snapshot]);

  useEffect(() => {
    if (!graphData?.nodes?.length) {
      setSelectedNodeId('');
      return;
    }

    setSelectedNodeId((prev) => {
      if (prev && graphData.nodes.some((node) => node.id === prev)) return prev;
      return graphData.nodes[0].id;
    });
  }, [graphData]);

  const selectedNode = useMemo(() => {
    if (!graphData?.nodes) return null;
    return graphData.nodes.find((node) => node.id === selectedNodeId) || null;
  }, [graphData, selectedNodeId]);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <GitBranch className="w-7 h-7 text-white" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold text-white tracking-tight">Architecture</h2>
            <p className="text-sm text-slate-400 mt-1">
              Auto-generated, read-only system map (UI to Logic to Data to External integrations).
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => loadSnapshot(true, false)}
            className="px-4 py-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-xs font-bold uppercase tracking-widest inline-flex items-center gap-2 hover:bg-emerald-500/20 transition-colors"
            disabled={refreshing}
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="glass-card p-4 border-sky-500/20 bg-slate-900/40">
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <span className="text-slate-300">View: <span className="text-white font-semibold">Readable</span></span>
          <span className="text-slate-300">Zoom: <span className="text-white font-semibold">{zoomPercent}%</span></span>
          <span className="text-slate-300">Last updated: <span className="text-white font-semibold">{formatTimeLabel(lastUpdated)}</span></span>
          <span className="text-slate-400">Auto-refresh: {AUTO_REFRESH_MS / 1000}s</span>
          <span className="text-slate-400">Files: {snapshot?.summary?.files_scanned ?? '—'}</span>
          <span className="text-slate-400">Nodes: {graphData?.summary?.nodes ?? '—'}</span>
          <span className="text-slate-400">Edges: {graphData?.summary?.edges ?? '—'}</span>
        </div>
      </div>

      <div className="glass-card p-5 border-emerald-500/20 bg-slate-900/45">
        <div className="flex items-center gap-2 mb-4">
          <Workflow className="w-5 h-5 text-emerald-400" />
          <p className="text-sm font-extrabold text-white uppercase tracking-widest">How Things Execute</p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {EXECUTION_GUIDES.map((guide) => (
            <div key={guide.id} className="rounded-xl border border-slate-700/70 bg-slate-900/70 p-4">
              <p className="text-xs font-bold text-emerald-300 uppercase tracking-widest mb-3">{guide.title}</p>
              <ol className="space-y-2 text-xs text-slate-300 leading-relaxed list-decimal pl-4">
                {guide.steps.map((step, idx) => (
                  <li key={`${guide.id}-${idx}`}>{step}</li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="glass-card p-4 border-rose-500/30 bg-rose-500/10 text-rose-300 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="glass-card min-h-[420px] flex items-center justify-center text-slate-400">
          <span className="inline-flex items-center gap-3">
            <RefreshCw className="w-5 h-5 animate-spin" /> Generating architecture graph...
          </span>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <section className="xl:col-span-8 space-y-4">
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setZoomPercent((prev) => Math.max(50, prev - 10))}
                className="px-3 py-2 rounded-xl border border-slate-700/70 bg-slate-800/60 text-slate-200 text-xs font-bold uppercase tracking-widest inline-flex items-center gap-2 hover:bg-slate-700/70 transition-colors"
                title="Zoom out"
                aria-label="Zoom out architecture diagram"
              >
                <Minus className="w-4 h-4" /> Zoom Out
              </button>
              <button
                type="button"
                onClick={() => setZoomPercent(100)}
                className="px-3 py-2 rounded-xl border border-slate-700/70 bg-slate-800/60 text-slate-200 text-xs font-bold uppercase tracking-widest hover:bg-slate-700/70 transition-colors"
                title="Reset zoom"
                aria-label="Reset architecture diagram zoom"
              >
                100%
              </button>
              <button
                type="button"
                onClick={() => setZoomPercent((prev) => Math.min(200, prev + 10))}
                className="px-3 py-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-xs font-bold uppercase tracking-widest inline-flex items-center gap-2 hover:bg-emerald-500/20 transition-colors"
                title="Zoom in"
                aria-label="Zoom in architecture diagram"
              >
                <Plus className="w-4 h-4" /> Zoom In
              </button>
            </div>

            <ArchitectureDiagram
              snapshot={graphData}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
              svgRef={svgRef}
              fitToView={false}
              zoom={zoomPercent / 100}
            />

            <div className="glass-card p-4 border-slate-800/70 bg-slate-900/50">
              <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Layer Legend</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
                {(graphData?.layers || []).map((layer) => (
                  <div key={layer.id} className="flex items-center gap-2 rounded-lg border border-slate-700/60 bg-slate-900/70 px-3 py-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: layer.color }} />
                    <span className="text-slate-200 font-semibold">{layer.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <aside className="xl:col-span-4 space-y-4">
            <div className="glass-card p-5 border-emerald-500/20 bg-slate-900/40">
              <div className="flex items-center gap-2 mb-4">
                <FileCode2 className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-extrabold text-white uppercase tracking-widest">Node Details</h3>
              </div>

              {!selectedNode ? (
                <p className="text-sm text-slate-400">Select any node in the diagram to inspect module metadata.</p>
              ) : (
                <div className="space-y-3 text-sm">
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase tracking-widest">Module</p>
                    <p className="text-white font-bold mt-1 break-all">{selectedNode.label}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase tracking-widest">File Path</p>
                    <p className="text-slate-300 mt-1 break-all">{selectedNode.path}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-lg border border-slate-700/60 bg-slate-900/70 px-3 py-2">
                      <p className="text-slate-500 uppercase">Role</p>
                      <p className="text-white font-semibold mt-1">{String(selectedNode.role || 'module').replace(/_/g, ' ')}</p>
                    </div>
                    <div className="rounded-lg border border-slate-700/60 bg-slate-900/70 px-3 py-2">
                      <p className="text-slate-500 uppercase">Layer</p>
                      <p className="text-white font-semibold mt-1 capitalize">{selectedNode.layer}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="glass-card p-5 border-slate-800/70 bg-slate-900/45">
              <div className="flex items-center gap-2 mb-3">
                <Package className="w-4 h-4 text-sky-400" />
                <p className="text-xs font-bold uppercase tracking-widest text-slate-300">Exports</p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(selectedNode?.exports || []).slice(0, 20).map((item) => (
                  <span key={item} className="px-2 py-1 rounded-md bg-sky-500/10 border border-sky-500/20 text-[10px] text-sky-300 font-semibold">
                    {item}
                  </span>
                ))}
                {!(selectedNode?.exports || []).length && (
                  <span className="text-xs text-slate-500">No exported symbols detected.</span>
                )}
              </div>
            </div>

            <div className="glass-card p-5 border-slate-800/70 bg-slate-900/45">
              <div className="flex items-center gap-2 mb-3">
                <Link2 className="w-4 h-4 text-amber-400" />
                <p className="text-xs font-bold uppercase tracking-widest text-slate-300">Key Dependencies</p>
              </div>
              <div className="space-y-2 max-h-44 overflow-auto custom-scrollbar pr-1">
                {(selectedNode?.dependencies || []).slice(0, 25).map((dep) => (
                  <div key={dep} className="text-xs text-slate-300 rounded-md border border-slate-700/60 bg-slate-900/70 px-2 py-1.5 break-all">
                    {dep}
                  </div>
                ))}
                {!(selectedNode?.dependencies || []).length && (
                  <span className="text-xs text-slate-500">No dependencies detected.</span>
                )}
              </div>
            </div>

            <div className="glass-card p-5 border-slate-800/70 bg-slate-900/45">
              <div className="flex items-center gap-2 mb-3">
                <Layers className="w-4 h-4 text-violet-400" />
                <p className="text-xs font-bold uppercase tracking-widest text-slate-300">State / Events / API</p>
              </div>
              <div className="space-y-2 text-xs text-slate-300">
                <p>State hooks: <span className="text-white font-semibold">{selectedNode?.metadata?.state_count ?? 0}</span></p>
                <p>Event props: <span className="text-white font-semibold">{(selectedNode?.metadata?.event_props || []).join(', ') || 'None'}</span></p>
                <p className="text-slate-400 mt-2">API calls:</p>
                <div className="space-y-1 max-h-24 overflow-auto custom-scrollbar pr-1">
                  {(selectedNode?.metadata?.api_calls || []).slice(0, 8).map((call, idx) => (
                    <div key={`${call}-${idx}`} className="text-[11px] text-slate-300 rounded-md border border-slate-700/60 bg-slate-900/70 px-2 py-1 break-all">
                      {call}
                    </div>
                  ))}
                  {!(selectedNode?.metadata?.api_calls || []).length && (
                    <span className="text-xs text-slate-500">No API calls detected.</span>
                  )}
                </div>
              </div>
            </div>
          </aside>
        </div>
      )}

    </div>
  );
}
