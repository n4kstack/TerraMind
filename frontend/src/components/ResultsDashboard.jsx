import React from 'react';
import { XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid, PieChart, Pie, Cell } from 'recharts';
import {
  Sprout, TrendingUp, TrendingDown, Minus, Droplets, Sun, CloudRain,
  Activity, Shield, AlertTriangle, CheckCircle2, BarChart3, MapPin
} from 'lucide-react';

const COLORS = ['#10b981', '#0ea5e9', '#8b5cf6', '#f59e0b', '#f43f5e', '#06b6d4', '#ec4899'];

function Card({ title, icon: Icon, iconColor = 'emerald', children, className = '' }) {
  return (
    <div className={`glass-card p-5 ${className}`}>
      <div className="flex items-center gap-2.5 mb-4">
        {Icon && <Icon className={`w-5 h-5 text-${iconColor}-400`} />}
        <h3 className="text-base font-bold text-white">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function TrendIcon({ trend }) {
  if (trend === 'improving') return <TrendingUp className="w-4 h-4 text-emerald-400" />;
  if (trend === 'declining') return <TrendingDown className="w-4 h-4 text-rose-400" />;
  return <Minus className="w-4 h-4 text-slate-400" />;
}

export default function ResultsDashboard({ result }) {
  if (!result) return null;

  const { crop_recommender, yield_predictor, agri_condition_advisor, district_intelligence, execution_mode, adaptation_applied, sync_status, latency_ms, system_notes } = result;

  const traj = district_intelligence?.ten_year_trajectory_data;
  const trajData = traj ? traj.years.map((y, i) => ({ year: y, yield: traj.yields[i] })) : [];

  // Irrigation infra for pie
  const infraData = district_intelligence?.irrigation_infrastructure_data;
  const pieData = infraData
    ? Object.entries(infraData).filter(([k, v]) => k !== 'net_irrigated' && v > 0)
        .map(([k, v]) => ({ name: k.replace(/_/g, ' '), value: Math.round(v * 100) / 100 }))
    : [];

  return (
    <div className="space-y-5 animate-in">
      {/* Header badges */}
      <div className="flex flex-wrap items-center gap-3">
        <span className={`mode-badge mode-${execution_mode === 'local_only' ? 'local' : execution_mode}`}>
          {execution_mode} mode
        </span>
        {adaptation_applied && (
          <span className="mode-badge bg-violet-500/20 text-violet-300 border border-violet-500/30">
            ✦ Local Adapted
          </span>
        )}
        <span className="text-xs text-slate-500 ml-auto">
          ⚡ {latency_ms}ms • v{result.model_version}
        </span>
      </div>

      {/* Top-3 Crops */}
      <Card title="Top-3 Crop Recommendations" icon={Sprout} iconColor="emerald">
        <div className="space-y-3 mb-4">
          {crop_recommender.top_3.map((c, i) => (
            <div key={i} className="flex items-center gap-3">
              <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm font-bold ${
                i === 0 ? 'bg-emerald-500/20 text-emerald-400' :
                i === 1 ? 'bg-sky-500/20 text-sky-400' : 'bg-violet-500/20 text-violet-400'
              }`}>{i + 1}</span>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-white capitalize">{c.crop}</span>
                  <span className="text-sm font-mono text-emerald-400">{(c.final_confidence * 100).toFixed(1)}%</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                  <div className="confidence-bar" style={{ width: `${Math.min(c.final_confidence * 100, 100)}%` }} />
                </div>
                {c.local_adjustment !== 0 && (
                  <span className="text-xs text-slate-500 mt-0.5 inline-block">
                    base: {(c.base_confidence * 100).toFixed(1)}% | adjustment: {c.local_adjustment > 0 ? '+' : ''}{(c.local_adjustment * 100).toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Yield Prediction */}
      <Card title="Yield Prediction" icon={BarChart3} iconColor="sky">
        {yield_predictor.expected_yield != null ? (
          <div>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-3xl font-bold text-white">{yield_predictor.expected_yield.toFixed(2)}</span>
              <span className="text-sm text-slate-400">{yield_predictor.unit}</span>
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-400 mb-2">
              <span>Lower: <span className="text-amber-400 font-mono">{yield_predictor.confidence_band.lower?.toFixed(2) ?? '—'}</span></span>
              <span>Upper: <span className="text-emerald-400 font-mono">{yield_predictor.confidence_band.upper?.toFixed(2) ?? '—'}</span></span>
            </div>
            <p className="text-xs text-slate-500">{yield_predictor.explanation}</p>
          </div>
        ) : (
          <p className="text-slate-500 text-sm">{yield_predictor.explanation || 'Yield data unavailable'}</p>
        )}
      </Card>

      {/* Agri Condition Advisor */}
      <Card title="Agronomic Conditions" icon={Sun} iconColor="amber">
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div className="bg-slate-800/50 rounded-xl p-3 text-center">
            <Sun className="w-5 h-5 text-amber-400 mx-auto mb-1" />
            <div className="text-lg font-bold text-white">{agri_condition_advisor.sunlight_hours ?? '—'}h</div>
            <div className="text-xs text-slate-400">Sunlight</div>
          </div>
          <div className="bg-slate-800/50 rounded-xl p-3 text-center">
            <Droplets className="w-5 h-5 text-sky-400 mx-auto mb-1" />
            <div className="text-lg font-bold text-white capitalize">{agri_condition_advisor.irrigation_type}</div>
            <div className="text-xs text-slate-400">Irrigation Type</div>
          </div>
          <div className="bg-slate-800/50 rounded-xl p-3 text-center">
            <CloudRain className="w-5 h-5 text-blue-400 mx-auto mb-1" />
            <div className="text-lg font-bold text-white capitalize">{agri_condition_advisor.irrigation_need}</div>
            <div className="text-xs text-slate-400">Irrigation Need</div>
          </div>
        </div>
        {agri_condition_advisor.district_prior_used && (
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2 text-xs text-emerald-300 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{agri_condition_advisor.explanation}</span>
          </div>
        )}
        {agri_condition_advisor.crop_irrigated_pct != null && (
          <p className="text-xs text-slate-500 mt-2">
            Historical irrigated area for this crop in district: <span className="text-sky-400 font-mono">{agri_condition_advisor.crop_irrigated_pct}%</span>
          </p>
        )}
      </Card>

      {/* District Intelligence */}
      <Card title="District Intelligence" icon={MapPin} iconColor="violet">
        <div className="space-y-3 text-sm">
          {district_intelligence.district_crop_share_percent != null && (
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Crop area share in district</span>
              <span className="font-bold text-emerald-400">{district_intelligence.district_crop_share_percent}%</span>
            </div>
          )}
          {district_intelligence.yield_trend && (
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Yield trend</span>
              <span className="flex items-center gap-1.5 font-semibold capitalize">
                <TrendIcon trend={district_intelligence.yield_trend} />
                {district_intelligence.yield_trend}
              </span>
            </div>
          )}
          {district_intelligence.best_historical_season && (
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Best historical season</span>
              <span className="text-amber-400 font-semibold capitalize">{district_intelligence.best_historical_season}</span>
            </div>
          )}
          {district_intelligence.top_competing_crops?.length > 0 && (
            <div>
              <span className="text-slate-400 block mb-1.5">Competing crops</span>
              <div className="flex flex-wrap gap-1.5">
                {district_intelligence.top_competing_crops.map((c, i) => (
                  <span key={i} className="px-2.5 py-1 bg-slate-800 rounded-lg text-xs font-medium text-slate-200 capitalize">{c}</span>
                ))}
              </div>
            </div>
          )}
          {district_intelligence.crop_irrigated_area_percent != null && (
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Crop irrigated area</span>
              <span className="text-sky-400 font-mono">{district_intelligence.crop_irrigated_area_percent}%</span>
            </div>
          )}
          {district_intelligence.ten_year_trajectory_summary && (
            <div className="bg-slate-800/40 rounded-lg p-3 text-xs text-slate-300">
              📈 {district_intelligence.ten_year_trajectory_summary}
            </div>
          )}
          {district_intelligence.irrigation_infrastructure_summary && (
            <div className="bg-slate-800/40 rounded-lg p-3 text-xs text-slate-300">
              💧 {district_intelligence.irrigation_infrastructure_summary}
            </div>
          )}
        </div>

        {/* Trajectory chart */}
        {trajData.length > 2 && (
          <div className="mt-4">
            <p className="text-xs text-slate-500 mb-2 font-medium">10-Year Yield Trajectory</p>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={trajData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="year" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, color: '#f1f5f9' }} />
                <Line type="monotone" dataKey="yield" stroke="#10b981" strokeWidth={2} dot={{ fill: '#10b981', r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Irrigation pie */}
        {pieData.length > 0 && (
          <div className="mt-4">
            <p className="text-xs text-slate-500 mb-2 font-medium">Irrigation Infrastructure</p>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                  outerRadius={70} innerRadius={30} paddingAngle={2}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={{ stroke: '#64748b' }}
                >
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, color: '#f1f5f9' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* Sync & System Info */}
      <Card title="System Info" icon={Activity} iconColor="sky">
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-400">Mode</span><span className="capitalize font-medium">{execution_mode}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Version</span><span className="font-mono">{result.model_version}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Adapted</span><span>{adaptation_applied ? '✅ Yes' : '—'}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Latency</span><span className="font-mono">{latency_ms}ms</span></div>
          {sync_status && (
            <>
              <div className="flex justify-between"><span className="text-slate-400">Edge ver.</span><span className="font-mono">{sync_status.edge_version}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Central ver.</span><span className="font-mono">{sync_status.central_version}</span></div>
              {sync_status.stale && (
                <div className="col-span-2 flex items-center gap-1.5 text-amber-400 text-xs mt-1">
                  <AlertTriangle className="w-3.5 h-3.5" /> Edge cache may be stale — consider syncing
                </div>
              )}
            </>
          )}
        </div>
      </Card>

      {/* Adaptation explanation */}
      {crop_recommender.adaptation_factors?.length > 0 && (
        <Card title="Why This Recommendation?" icon={Shield} iconColor="violet">
          <ul className="space-y-1.5">
            {crop_recommender.adaptation_factors.map((f, i) => (
              <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                <span className="text-violet-400 mt-0.5">•</span> {f}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* System notes */}
      {system_notes?.length > 0 && (
        <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-xs text-amber-300 space-y-1">
          {system_notes.map((n, i) => <p key={i}>⚠ {n}</p>)}
        </div>
      )}
    </div>
  );
}
