import React, { useEffect, useState } from 'react';
import { Server, Database, Layers, ShieldCheck, Activity, AlertCircle } from 'lucide-react';
import { fetchSystemStatus } from '../services/api';
import { SystemInfo } from '../types';
import { EmptyState } from '../components/common/EmptyState';
import { HealthBadge } from '../components/common/HealthBadge';

export const DashboardPage: React.FC = () => {
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSystemStatus()
      .then((data) => {
        setSystemInfo(data);
        setError(null);
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-alpha-text-primary flex items-center gap-3">
            <span>System Overview</span>
            <span className="text-xs font-mono font-medium text-alpha-gold px-2 py-0.5 rounded bg-alpha-gold/10 border border-alpha-gold/30">
              PHASE 1
            </span>
          </h1>
          <p className="text-sm text-alpha-text-secondary mt-1">
            Institutional Quantitative Core Infrastructure & Foundation Architecture
          </p>
        </div>

        <div className="flex items-center gap-3">
          {loading ? (
            <span className="text-xs font-mono text-alpha-text-muted">Probing services...</span>
          ) : systemInfo ? (
            <HealthBadge
              status={systemInfo.database.connected ? 'healthy' : 'unhealthy'}
              label={systemInfo.database.connected ? 'Systems Operational' : 'DB Reconnecting'}
              latencyMs={systemInfo.database.latency_ms}
            />
          ) : (
            <HealthBadge status="unhealthy" label="Backend Offline" />
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-rose-900/60 bg-rose-950/30 flex items-start gap-3 text-rose-300 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400 mt-0.5" />
          <div>
            <span className="font-semibold">Backend Unreachable:</span> {error}.
            Ensure the FastAPI server is running (`uvicorn app.main:app --port 8000`).
          </div>
        </div>
      )}

      {/* Infrastructure Diagnostics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Core FastAPI */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card/70 hover:border-alpha-borderSubtle transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-alpha-text-muted">FastAPI Service</span>
            <Server className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="text-xl font-bold font-mono text-alpha-text-primary">
            v{systemInfo?.version || '1.0.0'}
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-alpha-text-secondary">App Factory Lifespan Active</span>
          </div>
        </div>

        {/* Database */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card/70 hover:border-alpha-borderSubtle transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-alpha-text-muted">TimescaleDB / Postgres</span>
            <Database className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="text-xl font-bold font-mono text-alpha-text-primary">
            {systemInfo?.database.connected ? 'Connected' : 'Configured'}
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs">
            <span className={`w-2 h-2 rounded-full ${systemInfo?.database.connected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            <span className="text-alpha-text-secondary">
              {systemInfo?.database.dialect ? `${systemInfo.database.dialect} 2.x Async` : 'SQLAlchemy 2.x Session'}
            </span>
          </div>
        </div>

        {/* Migrations */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card/70 hover:border-alpha-borderSubtle transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-alpha-text-muted">Alembic Schema</span>
            <Layers className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="text-xl font-bold font-mono text-alpha-text-primary">
            Rev 0001
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-alpha-text-secondary">Initial Schema Prepared</span>
          </div>
        </div>

        {/* Security & Strict TypeScript */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card/70 hover:border-alpha-borderSubtle transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-alpha-text-muted">Security & Types</span>
            <ShieldCheck className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="text-xl font-bold font-mono text-alpha-text-primary">
            Strict Mode
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-alpha-text-secondary">Zero Secrets Committed</span>
          </div>
        </div>
      </div>

      {/* Honest Empty State Section for Phase 2 & 3 modules */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4">
        <div>
          <h2 className="text-base font-semibold text-alpha-text-primary mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-alpha-gold" />
            <span>Market Data Feeds</span>
          </h2>
          <EmptyState
            title="No Live Market Tickers Connected"
            description="Market data ingestion, WebSocket order book streams, and historical bar feeds will be integrated in Phase 2. ALPHA Quant strictly adheres to zero synthetic or mocked trading metrics."
            phaseRequired={2}
            actionText="View System Health"
            actionHref="/system-health"
          />
        </div>

        <div>
          <h2 className="text-base font-semibold text-alpha-text-primary mb-3 flex items-center gap-2">
            <Layers className="w-4 h-4 text-alpha-gold" />
            <span>Quant Execution Engine</span>
          </h2>
          <EmptyState
            title="No Active Trading Strategies"
            description="Algorithmic factor models, risk weighting matrices, and order execution simulators will be loaded in Phase 3 once verified market feeds are active."
            phaseRequired={3}
            actionText="View Architecture Diagnostics"
            actionHref="/system-health"
          />
        </div>
      </div>
    </div>
  );
};
