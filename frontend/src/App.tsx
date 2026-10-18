import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { OverviewPage } from './pages/OverviewPage';

const MarketsPage = lazy(() => import('./pages/MarketsPage').then((m) => ({ default: m.MarketsPage })));
const StrategiesPage = lazy(() => import('./pages/StrategiesPage').then((m) => ({ default: m.StrategiesPage })));
const BacktestPage = lazy(() => import('./pages/BacktestPage').then((m) => ({ default: m.BacktestPage })));
const PaperTradingPage = lazy(() => import('./pages/PortfolioPage').then((m) => ({ default: m.PaperTradingPage })));
const RiskManagementPage = lazy(() => import('./pages/RiskManagementPage').then((m) => ({ default: m.RiskManagementPage })));
const ExperimentsPage = lazy(() => import('./pages/ExperimentsPage').then((m) => ({ default: m.ExperimentsPage })));
const SystemHealthPage = lazy(() => import('./pages/SystemHealthPage').then((m) => ({ default: m.SystemHealthPage })));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })));

const RouteFallback: React.FC = () => (
  <div className="flex items-center justify-center py-24 text-xs font-mono text-alpha-gold animate-pulse">
    LOADING TELEMETRY MODULE...
  </div>
);

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<AppShell />}>
            {/* 1. Overview */}
            <Route index element={<OverviewPage />} />
            <Route path="overview" element={<Navigate to="/" replace />} />

            {/* 2. Markets (with backward-compatible alias) */}
            <Route path="markets" element={<MarketsPage />} />
            <Route path="market-data" element={<Navigate to="/markets" replace />} />

            {/* 3. Strategies */}
            <Route path="strategies" element={<StrategiesPage />} />

            {/* 4. Backtesting (with backward-compatible alias) */}
            <Route path="backtesting" element={<BacktestPage />} />
            <Route path="backtests" element={<Navigate to="/backtesting" replace />} />

            {/* 5. Paper Trading (with backward-compatible alias) */}
            <Route path="paper-trading" element={<PaperTradingPage />} />
            <Route path="portfolio" element={<Navigate to="/paper-trading" replace />} />

            {/* 6. Risk Management */}
            <Route path="risk" element={<RiskManagementPage />} />

            {/* 7. Experiments */}
            <Route path="experiments" element={<ExperimentsPage />} />

            {/* 8. System Health (with alias) */}
            <Route path="system-health" element={<SystemHealthPage />} />
            <Route path="system" element={<Navigate to="/system-health" replace />} />

            {/* Fallback */}
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
};

export default App;

