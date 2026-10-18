import React, { useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  LineChart,
  Briefcase,
  ShieldAlert,
} from 'lucide-react';
import { AppSidebar } from './AppSidebar';
import { AppHeader } from './AppHeader';

export const AppShell: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const mobileQuickNav = [
    { name: 'Desk', path: '/', icon: LayoutDashboard },
    { name: 'Markets', path: '/markets', icon: TrendingUp },
    { name: 'Models', path: '/strategies', icon: LineChart },
    { name: 'Trade', path: '/paper-trading', icon: Briefcase },
    { name: 'Risk', path: '/risk', icon: ShieldAlert },
  ];

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-alpha-bg text-alpha-text-primary">
      {/* Sidebar Navigation */}
      <AppSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <AppHeader onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <main className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 sm:p-6 lg:p-8 pb-24 lg:pb-8 bg-alpha-bg">
          <Outlet />
        </main>

        {/* Mobile Bottom Quick-Navigation Bar (< 1024px) */}
        <nav
          aria-label="Mobile quick navigation"
          className="lg:hidden fixed bottom-0 left-0 right-0 z-30 bg-alpha-card/95 backdrop-blur-md border-t border-alpha-border px-1 py-1.5 pb-safe flex items-center justify-around shadow-2xl"
        >
          {mobileQuickNav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `flex flex-col items-center justify-center py-1 px-2.5 rounded-lg text-[10px] font-mono font-medium transition-colors min-w-[56px] ${
                    isActive
                      ? 'text-alpha-gold bg-alpha-gold/10'
                      : 'text-alpha-text-muted hover:text-white'
                  }`
                }
              >
                <Icon className="w-4 h-4 mb-0.5 shrink-0" />
                <span className="truncate">{item.name}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </div>
  );
};
