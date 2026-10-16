import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { DashboardPage } from './pages/DashboardPage';
import { MarketDataPage } from './pages/MarketDataPage';
import { PortfolioPage } from './pages/PortfolioPage';
import { StrategiesPage } from './pages/StrategiesPage';
import { BacktestPage } from './pages/BacktestPage';
import { SystemHealthPage } from './pages/SystemHealthPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="market-data" element={<MarketDataPage />} />
          <Route path="portfolio" element={<PortfolioPage />} />
          <Route path="strategies" element={<StrategiesPage />} />
          <Route path="backtests" element={<BacktestPage />} />
          <Route path="system-health" element={<SystemHealthPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
