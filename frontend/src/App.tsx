import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { OverviewPage } from './pages/OverviewPage';
import { MarketsPage } from './pages/MarketsPage';
import { StrategiesPage } from './pages/StrategiesPage';
import { BacktestPage } from './pages/BacktestPage';
import { PaperTradingPage } from './pages/PortfolioPage';
import { RiskManagementPage } from './pages/RiskManagementPage';
import { ExperimentsPage } from './pages/ExperimentsPage';
import { SystemHealthPage } from './pages/SystemHealthPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  );
};

export default App;
