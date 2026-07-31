import React from 'react';
import { NavLink } from 'react-router-dom';
import { Leaf, Sprout, Activity, Search, Zap, Award, Network, GitBranch } from 'lucide-react';

const NavItem = ({ to, icon: Icon, label, pulseOnActive = false }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 ${
        isActive
          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]'
          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border border-transparent'
      }`
    }
  >
    {({ isActive }) => (
      <>
        <Icon className={`w-4 h-4 ${pulseOnActive && isActive ? 'animate-pulse' : ''}`} />
        <span>{label}</span>
      </>
    )}
  </NavLink>
);

export default function Navbar({ modelMode, version }) {
  return (
    <nav className="sticky top-0 z-50 border-b border-slate-800/50 backdrop-blur-xl bg-slate-900/60 transition-all duration-300">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3 group cursor-pointer">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 via-lime-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 group-hover:scale-105 transition-transform duration-300">
              <Leaf className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-extrabold text-white tracking-tight">
                Terra<span className="text-emerald-400">Mind</span>
              </h1>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold hidden sm:block">Agriculture Intelligence</p>
            </div>
          </div>

          {/* Navigation Links */}
          <div className="hidden lg:flex items-center gap-1">
            <NavItem to="/" icon={Sprout} label="Advisor" />
            <NavItem to="/monitor" icon={Activity} label="Monitor" />
            <NavItem to="/diagnosis" icon={Search} label="Diagnosis" />
            <NavItem to="/graphrag" icon={Network} label="AugNosis" />
            <NavItem to="/architecture" icon={GitBranch} label="Architecture" pulseOnActive />
          </div>

          {/* Status Indicators */}
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-3">
              {modelMode === 'edge' && (
                <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-bold text-emerald-400 uppercase tracking-tighter shadow-sm shadow-emerald-500/5">
                  <Zap className="w-3 h-3" /> Edge Optimized
                </div>
              )}
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/50 border border-slate-700/50 text-[10px] font-bold text-slate-400 uppercase tracking-tighter">
                <Award className="w-3 h-3" /> v{version || '1.0.0'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
