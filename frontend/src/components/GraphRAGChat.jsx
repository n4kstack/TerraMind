import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Bot, Loader2, Send, ShieldCheck, Sprout, Network } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { graphRagService } from '../services/graphRagService';

const starterQueries = [
  'Wheat crop, humid weather, what pests are high risk now?',
  'How to control aphids in cotton during warm and dry conditions?',
  'Rice blast risk in monsoon and preventive fungicide plan?',
  'Is copper oxychloride safe in alkaline soil?',
];

// Normalise line endings only. Do NOT insert blank lines between single
// newlines - that splits markdown tables and tight lists into loose
// paragraphs. Block spacing is handled by the typography plugin.
function formatAssistantResponse(text) {
  if (!text) return '';

  return String(text)
    .replace(/\r\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// Tables can exceed the chat column, so each one scrolls inside its own
// container rather than forcing the whole bubble to scroll sideways.
const markdownComponents = {
  table: ({ node, ...props }) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-slate-700/60">
      <table className="w-full text-left text-xs border-collapse m-0" {...props} />
    </div>
  ),
  thead: ({ node, ...props }) => <thead className="bg-slate-900/70" {...props} />,
  th: ({ node, ...props }) => (
    <th
      className="px-3 py-2 font-semibold text-indigo-300 border-b border-slate-700/60 align-top"
      {...props}
    />
  ),
  td: ({ node, ...props }) => (
    <td className="px-3 py-2 border-b border-slate-800/60 align-top" {...props} />
  ),
  h2: ({ node, ...props }) => (
    <h2 className="text-sm font-bold text-white mt-5 mb-2 first:mt-0" {...props} />
  ),
  h3: ({ node, ...props }) => (
    <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-300 mt-4 mb-1.5" {...props} />
  ),
  code: ({ node, ...props }) => (
    <code className="px-1 py-0.5 rounded bg-slate-900/80 text-emerald-300 text-[11px]" {...props} />
  ),
};

function GraphRAGChat() {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState('');
  const [useLlm, setUseLlm] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [health, setHealth] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  useEffect(() => {
    graphRagService
      .health()
      .then(setHealth)
      .catch(() => setHealth({ status: 'degraded' }));
  }, []);

  const riskSummary = useMemo(() => {
    const context = lastResult?.context || {};
    return {
      pests: (context.high_risk_pests_now || []).length,
      diseases: (context.high_risk_diseases_now || []).length,
      warnings: (context.soil_conflicts || []).length + (context.tank_mix_warnings || []).length,
    };
  }, [lastResult]);

  const submitQuery = async (text) => {
    const input = (text ?? query).trim();
    if (!input || loading) return;

    setError('');
    setLoading(true);
    setMessages((prev) => [...prev, { role: 'user', content: input }]);

    try {
      const result = await graphRagService.query(input, useLlm);
      setLastResult(result);
      setMessages((prev) => [...prev, { role: 'assistant', content: result.response }]);
      setQuery('');
    } catch (err) {
      const msg = err?.message || 'AugNosis request failed';
      setError(msg);
      setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <section className="lg:col-span-8 glass-card border-indigo-500/10 flex flex-col h-[700px]">
        {/* Header */}
        <div className="border-b border-slate-800/50 p-6 bg-slate-900/40 backdrop-blur-xl shrink-0">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-indigo-500/10 rounded-2xl">
                 <Network className="h-6 w-6 text-indigo-400" />
              </div>
              <div>
                 <h2 className="text-xl font-black text-white tracking-tight uppercase">Knowledge Graph Terminal</h2>
                 <p className="mt-1 text-[10px] uppercase tracking-widest font-bold text-slate-500">Query AgroKG semantic index</p>
              </div>
            </div>
            <label className="flex items-center gap-3 cursor-pointer group">
              <div className="relative">
                 <input
                   type="checkbox"
                   checked={useLlm}
                   onChange={(e) => setUseLlm(e.target.checked)}
                   className="sr-only peer"
                 />
                 <div className="w-10 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 peer-checked:after:bg-indigo-400 after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all border border-slate-700 peer-checked:border-indigo-500/50 peer-checked:bg-indigo-500/20"></div>
              </div>
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest group-hover:text-indigo-400 transition-colors">LLM Generation</span>
            </label>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-900/30 custom-scrollbar relative">
          {messages.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center animate-in zoom-in duration-700">
               <div className="w-20 h-20 rounded-3xl bg-slate-800/50 border border-slate-700 flex items-center justify-center shadow-2xl mb-6 relative group overflow-hidden">
                   <div className="absolute inset-0 bg-indigo-500/10 animate-pulse" />
                   <Network className="w-10 h-10 text-indigo-500 relative group-hover:scale-110 transition-transform" />
               </div>
               <h3 className="text-xl font-black text-white tracking-tight italic uppercase mb-3">Graph Synthesis Engine Ready</h3>
               <p className="text-sm font-medium text-slate-500 max-w-sm leading-relaxed">
                  Query the localized agronomic knowledge graph. Mention a specific crop, weather condition, or symptom for targeted retrieval.
               </p>
            </div>
          )}

          {messages.map((m, idx) => (
            <div
              key={`${m.role}-${idx}`}
              className={`flex gap-4 animate-in fade-in slide-in-from-bottom-2 ${
                 m.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
               {m.role === 'assistant' && (
                  <div className="shrink-0 w-10 h-10 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mt-1">
                     <Bot className="w-5 h-5" />
                  </div>
               )}
               <div
                  className={`max-w-[85%] rounded-2xl px-5 py-3.5 text-sm shadow-md border ${
                     m.role === 'user'
                     ? 'bg-indigo-600 text-white rounded-tr-none border-indigo-500 shadow-indigo-600/20'
                     : 'bg-slate-800/80 text-slate-200 rounded-tl-none border-slate-700/50 backdrop-blur-md'
                  }`}
               >
                  {m.role === 'assistant' ? (
                    <div className="prose prose-invert prose-sm max-w-none prose-p:my-2.5 prose-p:leading-relaxed prose-strong:text-white prose-strong:font-semibold prose-ul:my-2 prose-ul:pl-4 prose-ol:my-2 prose-ol:pl-4 prose-li:my-0.5 prose-li:leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                        {formatAssistantResponse(m.content)}
                      </ReactMarkdown>
                     </div>
                  ) : (
                     <div className="font-medium whitespace-pre-wrap">{m.content}</div>
                  )}
               </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-4 justify-start animate-in fade-in">
                <div className="shrink-0 w-10 h-10 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mt-1">
                     <Loader2 className="w-5 h-5 animate-spin" />
                </div>
                <div className="bg-slate-800/50 border border-slate-700/30 rounded-2xl rounded-tl-none px-5 py-4 flex items-center gap-3">
                   <div className="flex gap-1.5">
                      <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                      <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                      <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" />
                   </div>
                   <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-none">Graph Traversal Active...</span>
                </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-slate-800/50 p-6 bg-slate-900/40 shrink-0">
          <div className="flex flex-wrap gap-2 mb-4">
            {starterQueries.slice(0, 3).map((q) => (
              <button
                key={q}
                onClick={() => submitQuery(q)}
                disabled={loading}
                className="rounded-full border border-indigo-500/20 bg-indigo-500/5 px-4 py-1.5 text-[10px] font-bold text-indigo-400 uppercase tracking-widest hover:bg-indigo-500/10 disabled:opacity-50 transition-colors shadow-none"
              >
                {q.substring(0, 40)}...
              </button>
            ))}
          </div>

          <div className="flex items-center gap-4 relative">
             <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                <ShieldCheck className="w-5 h-5" />
             </div>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submitQuery()}
              placeholder="Query the multi-hop causal graph..."
              className="w-full bg-slate-950/80 border border-slate-700/50 rounded-2xl pl-12 pr-4 py-3.5 text-sm text-white focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 outline-none disabled:opacity-50 transition-all placeholder:text-slate-600 shadow-inner"
            />
            <button
              onClick={() => submitQuery()}
              disabled={loading || !query.trim()}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white p-3.5 rounded-2xl transition-all shadow-lg shadow-indigo-600/20 disabled:shadow-none disabled:text-slate-500 group flex items-center justify-center shrink-0"
            >
              <Send className="w-5 h-5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
            </button>
          </div>

          {error && (
            <div className="mt-4 flex items-center gap-3 rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-xs font-bold text-rose-400 uppercase tracking-widest animate-in shake">
              <AlertTriangle className="h-5 w-5 shrink-0" /> 
              <span>{error}</span>
            </div>
          )}
        </div>
      </section>

      {/* Sidebar */}
      <aside className="lg:col-span-4 space-y-6">
        <div className="glass-card p-6 border-slate-800/50">
          <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-4 flex items-center gap-2">
             <Bot className="w-4 h-4 text-indigo-400" />
             Graph Engine Telemetry
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-xl border border-slate-800">
               <span className="text-xs text-slate-400 font-medium">Status</span>
               <div className="flex items-center gap-2">
                   <div className={`w-2 h-2 rounded-full animate-pulse ${health?.status === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                   <span className="text-xs font-bold text-white uppercase tracking-widest">{health?.status || 'awaiting'}</span>
               </div>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-xl border border-slate-800">
               <span className="text-xs text-slate-400 font-medium">Active Tensor Model</span>
               <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest">{health?.model || 'qwen2.5:1.5b'}</span>
            </div>
          </div>
        </div>

        <div className="glass-card p-6 border-slate-800/50 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
              <Sprout className="w-24 h-24 text-rose-500" />
          </div>
          <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-6 relative z-10">
             Extracted Causal Risks
          </h3>
          <div className="grid grid-cols-2 gap-4 relative z-10">
            <div className="bg-rose-500/5 border border-rose-500/10 rounded-2xl p-4 text-center">
              <div className="text-3xl font-black text-rose-500">{riskSummary.pests}</div>
              <div className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mt-1">Hostile Pests</div>
            </div>
            <div className="bg-amber-500/5 border border-amber-500/10 rounded-2xl p-4 text-center">
              <div className="text-3xl font-black text-amber-500">{riskSummary.diseases}</div>
              <div className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mt-1">Pathogens</div>
            </div>
            <div className="col-span-2 bg-indigo-500/5 border border-indigo-500/10 rounded-2xl p-4 text-center flex items-center justify-center gap-4">
              <div className="text-3xl font-black text-indigo-400">{riskSummary.warnings}</div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 text-left">Synthesis<br/>Warnings</div>
            </div>
          </div>
        </div>

        {lastResult?.parsed_intent && (
            <div className="glass-card p-6 border-slate-800/50 animate-in fade-in zoom-in duration-500">
            <h3 className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-4">
                <Network className="h-4 w-4 text-sky-400" /> Intent Resolution
            </h3>
            <div className="bg-slate-900/80 rounded-xl p-4 border border-slate-800 max-h-48 overflow-auto custom-scrollbar">
                <pre className="text-[10px] font-mono text-sky-300 leading-relaxed">
{JSON.stringify(lastResult.parsed_intent, null, 2)}
                </pre>
            </div>
            </div>
        )}
      </aside>
    </div>
  );
}

export default GraphRAGChat;
