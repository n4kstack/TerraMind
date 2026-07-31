import React, { useState, useEffect } from 'react';
import { fetchStates, fetchDistricts } from '../services/api';
import { Sprout, MapPin, Droplets, Thermometer, Wind, FlaskConical, Wheat, Layers } from 'lucide-react';

const SOIL_TYPES = ['loamy', 'sandy', 'clay', 'black', 'red', 'alluvial', 'laterite', 'chalky', 'peaty', 'saline'];
const SEASONS = ['kharif', 'rabi', 'summer', 'winter', 'whole year', 'autumn'];

export default function PredictionForm({ onSubmit, loading }) {
  const [states, setStates] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [form, setForm] = useState({
    N: 90, P: 42, K: 43, ph: 6.5,
    temperature: 25, humidity: 80, rainfall: 200,
    soil_type: 'loamy', state: '', district: '',
    season: 'kharif', area: '', mode: 'central',
  });

  useEffect(() => {
    fetchStates().then(setStates).catch(() => setStates([]));
  }, []);

  useEffect(() => {
    if (form.state) {
      fetchDistricts(form.state).then(setDistricts).catch(() => setDistricts([]));
      setForm(f => ({ ...f, district: '' }));
    }
  }, [form.state]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const payload = {
      ...form,
      N: parseFloat(form.N), P: parseFloat(form.P), K: parseFloat(form.K),
      ph: parseFloat(form.ph), temperature: parseFloat(form.temperature),
      humidity: parseFloat(form.humidity), rainfall: parseFloat(form.rainfall),
      area: form.area ? parseFloat(form.area) : null,
    };
    onSubmit(payload);
  };

  const inputClass = "w-full bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all";
  const selectClass = inputClass + " appearance-none cursor-pointer";
  const labelClass = "flex items-center gap-2 text-xs font-medium text-slate-300 mb-1.5";

  return (
    <form onSubmit={handleSubmit} className="glass-card p-6 lg:p-8 space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-lime-500 flex items-center justify-center">
          <Sprout className="w-5 h-5 text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">Pre-Sowing Advisor</h2>
          <p className="text-xs text-slate-400">Enter field conditions for crop recommendations</p>
        </div>
      </div>

      {/* Mode selector */}
      <div className="flex gap-2 p-1 bg-slate-800/60 rounded-xl">
        {[
          { value: 'central', label: 'Central', color: 'sky' },
          { value: 'edge', label: 'Edge', color: 'emerald' },
          { value: 'local_only', label: 'Local', color: 'amber' },
        ].map(m => (
          <button key={m.value} type="button"
            onClick={() => setForm(f => ({ ...f, mode: m.value }))}
            className={`flex-1 py-2 px-3 rounded-lg text-sm font-semibold transition-all ${
              form.mode === m.value
                ? `bg-${m.color}-500/20 text-${m.color}-400 ring-1 ring-${m.color}-500/30`
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* NPK row */}
      <div className="grid grid-cols-3 gap-3">
        <div><label className={`${labelClass} whitespace-nowrap`}><span className="inline-flex w-4 h-4 items-center justify-center text-base leading-none text-emerald-400 font-bold">N</span> (kg/ha)</label>
          <input name="N" type="number" step="any" value={form.N} onChange={handleChange} className={inputClass} required /></div>
        <div><label className={`${labelClass} whitespace-nowrap`}><span className="inline-flex w-4 h-4 items-center justify-center text-base leading-none text-sky-400 font-bold">P</span> (kg/ha)</label>
          <input name="P" type="number" step="any" value={form.P} onChange={handleChange} className={inputClass} required /></div>
        <div><label className={`${labelClass} whitespace-nowrap`}><span className="inline-flex w-4 h-4 items-center justify-center text-base leading-none text-violet-400 font-bold">K</span> (kg/ha)</label>
          <input name="K" type="number" step="any" value={form.K} onChange={handleChange} className={inputClass} required /></div>
      </div>

      {/* pH + temperature row */}
      <div className="grid grid-cols-2 gap-3">
        <div><label className={labelClass}><FlaskConical className="w-4 h-4 text-amber-400" /> pH</label>
          <input name="ph" type="number" step="0.1" value={form.ph} onChange={handleChange} className={inputClass} required /></div>
        <div><label className={labelClass}><Thermometer className="w-4 h-4 text-rose-400" /> Temperature (°C)</label>
          <input name="temperature" type="number" step="any" value={form.temperature} onChange={handleChange} className={inputClass} required /></div>
      </div>

      {/* Humidity + Rainfall */}
      <div className="grid grid-cols-2 gap-3">
        <div><label className={labelClass}><Wind className="w-4 h-4 text-sky-400" /> Humidity (%)</label>
          <input name="humidity" type="number" step="any" value={form.humidity} onChange={handleChange} className={inputClass} required /></div>
        <div><label className={labelClass}><Droplets className="w-4 h-4 text-blue-400" /> Rainfall (mm)</label>
          <input name="rainfall" type="number" step="any" value={form.rainfall} onChange={handleChange} className={inputClass} required /></div>
      </div>

      {/* Soil + Season */}
      <div className="grid grid-cols-2 gap-3">
        <div><label className={labelClass}><Layers className="w-4 h-4 text-amber-500" /> Soil Type</label>
          <select name="soil_type" value={form.soil_type} onChange={handleChange} className={selectClass}>
            {SOIL_TYPES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
          </select></div>
        <div><label className={labelClass}><Wheat className="w-4 h-4 text-lime-400" /> Season</label>
          <select name="season" value={form.season} onChange={handleChange} className={selectClass}>
            {SEASONS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
          </select></div>
      </div>

      {/* State + District */}
      <div className="grid grid-cols-2 gap-3">
        <div><label className={labelClass}><MapPin className="w-4 h-4 text-emerald-400" /> State</label>
          <select name="state" value={form.state} onChange={handleChange} className={selectClass} required>
            <option value="">Select state...</option>
            {states.map(s => <option key={s} value={s}>{s}</option>)}
          </select></div>
        <div><label className={labelClass}><MapPin className="w-4 h-4 text-teal-400" /> District</label>
          <select name="district" value={form.district} onChange={handleChange} className={selectClass} required>
            <option value="">Select district...</option>
            {districts.map(d => <option key={d} value={d}>{d}</option>)}
          </select></div>
      </div>

      {/* Area */}
      <div>
        <label className={labelClass}>Area (hectares, optional)</label>
        <input name="area" type="number" step="any" value={form.area} onChange={handleChange}
          className={inputClass} placeholder="e.g., 2.5" />
      </div>

      {/* Submit */}
      <button type="submit" disabled={loading}
        className={`w-full py-4 rounded-xl font-bold text-lg transition-all ${
          loading
            ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
            : 'bg-gradient-to-r from-emerald-600 to-lime-600 hover:from-emerald-500 hover:to-lime-500 text-white shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 active:scale-[0.98]'
        }`}>
        {loading ? (
          <span className="flex items-center justify-center gap-3">
            <div className="w-5 h-5 border-2 border-slate-400 border-t-emerald-400 rounded-full animate-spin" />
            Analyzing...
          </span>
        ) : '🌱 Get Recommendation'}
      </button>
    </form>
  );
}
