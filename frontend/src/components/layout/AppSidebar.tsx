import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, TrendingUp, PieChart, LineChart, Activity, X } from 'lucide-react';
import { Logo } from '../common/Logo';

interface AppSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AppSidebar: React.FC<AppSidebarProps> = ({ isOpen, onClose }) => {
  const navItems = [
    {
      name: 'System Overview',
      path: '/',
      icon: LayoutDashboard,
      phase: 1,
      badge: 'Active',
    },
    {
      name: 'Market Data Feed',
      path: '/market-data',
      icon: TrendingUp,
      phase: 2,
      badge: 'Live Feed',
    },
    {
      name: 'Portfolio Engine',
      path: '/portfolio',
      icon: PieChart,
      phase: 2,
      badge: 'Phase 2',
    },
    {
      name: 'Quant Strategies',
      path: '/strategies',
      icon: LineChart,
      phase: 3,
      badge: 'Phase 3',
    },
    {
      name: 'System Diagnostics',
      path: '/system-health',
      icon: Activity,
      phase: 1,
      badge: 'Live',
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/80 z-40 lg:hidden backdrop-blur-sm transition-opacity"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed lg:static top-0 bottom-0 left-0 w-64 bg-alpha-bg border-r border-alpha-border flex flex-col z-50 transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Brand Header */}
        <div className="h-16 border-b border-alpha-border px-5 flex items-center justify-between">
          <Logo size="md" />
          <button
            onClick={onClose}
            aria-label="Close sidebar"
            className="lg:hidden p-1.5 rounded-lg text-alpha-text-muted hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 py-6 px-3 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-mono uppercase tracking-widest text-alpha-text-muted">
            Core Modules
          </div>

          {navItems.map((item) => {
            const Icon = item.icon;
            const isPhase1 = item.phase === 1;

            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => {
                  if (window.innerWidth < 1024) onClose();
                }}
                className={({ isActive }) =>
                  `flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-alpha-gold/15 text-alpha-gold border border-alpha-gold/30 shadow-sm'
                      : 'text-alpha-text-secondary hover:text-alpha-text-primary hover:bg-alpha-cardHover'
                  }`
                }
              >
                <div className="flex items-center gap-3">
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.name}</span>
                </div>

                <span
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                    isPhase1
                      ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40'
                      : 'bg-alpha-card text-alpha-text-muted border-alpha-borderSubtle'
                  }`}
                >
                  {item.badge}
                </span>
              </NavLink>
            );
          })}
        </div>

        {/* Footer Info */}
        <div className="p-4 border-t border-alpha-border bg-alpha-card/40">
          <div className="flex items-center justify-between text-xs text-alpha-text-muted">
            <span className="font-mono">ALPHA v1.0.0</span>
            <span className="inline-block w-2 h-2 rounded-full bg-alpha-gold animate-ping" />
          </div>
          <p className="text-[11px] text-alpha-text-muted mt-1 leading-snug">
            Institutional Quantitative System Foundation
          </p>
        </div>
      </aside>
    </>
  );
};
