import React, { useEffect, useState, useCallback } from 'react';
import {
  Activity,
  Server,
  Database,
  RefreshCw,
  Terminal,
  AlertTriangle,
  Radio,
  Zap,
} from 'lucide-react';
import {
  fetchHealth,
  fetchReadiness,
  fetchSystemStatus,
  fetchSystemAuditLogs,
  fetchMarketStatus,
  fetchPaperTradingStatus,
} from '../services/api';
import {
  HealthResponse,
  ReadinessResponse,
  SystemInfo,
  SystemAuditLog,
  MarketStatusResponse,
  PaperTradingStatus,
} from '../types';
import { HealthBadge } from '../components/common/HealthBadge';

export const SystemHealthPage: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [marketStatus, setMarketStatus] = useState<MarketStatusResponse | null>(null);
  const [orchestratorStatus, setOrchestratorStatus] = useState<PaperTradingStatus | null>(null);
  const [auditLogs, setAuditLogs] = useState<SystemAuditLog[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const runDiagnostics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, r, s, m, o, logs] = await Promise.all([
        fetchHealth().catch(() => null),
        fetchReadiness().catch(() => null),
        fetchSystemStatus().catch(() => null),
        fetchMarketStatus('BTCUSDT', '1m').catch(() => null),
        fetchPaperTradingStatus().catch(() => null),
        fetchSystemAuditLogs(30).catch(() => []),
      ]);
      setHealth(h);
      setReadiness(r);
      setSystemInfo(s);
      setMarketStatus(m);
      setOrchestratorStatus(o);
      setAuditLogs(logs);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Diagnostic probe failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    runDiagnostics();
    const intervalTimer = window.setInterval(runDiagnostics, 5000);
    return () => clearInterval(intervalTimer);
  }, [runDiagnostics]);

  // Compute collector lag
  const lastExchangeTime = marketStatus?.last_exchange_time ? new Date(marketStatus.last_exchange_time).getTime() : null;
  const collectorLagSeconds = lastExchangeTime ? Math.max(0, Math.round((Date.now() - lastExchangeTime) / 1000)) : null;

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
              <Activity className="w-6 h-6 text-alpha-gold" />
              <span>SYSTEM HEALTH & DIAGNOSTICS</span>
            </h1>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-alpha-gold/10 text-alpha-gold border border-alpha-gold/30">
              KUBERNETES READY
            </span>
          </div>
          <p className="text-xs text-alpha-text-secondary mt-1 font-mono">
            Collector Lag • Reconnect Counters • TimescaleDB Health • Lifecycle Worker Status
          </p>
        </div>

        <button
          onClick={runDiagnostics}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-mono font-medium rounded-lg bg-alpha-gold/15 text-alpha-gold border border-alpha-gold/30 hover:bg-alpha-gold/25 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Run Probes</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-rose-900/60 bg-rose-950/30 flex items-start gap-3 text-rose-300 text-xs font-mono">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-400 mt-0.5" />
          <div>
            <span className="font-semibold">Diagnostic Failure:</span> {error}
          </div>
        </div>
      )}

      {/* Probes Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Core Liveness Probe */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono uppercase text-alpha-text-muted">Liveness Probe</span>
              <Server className="w-4 h-4 text-alpha-gold" />
            </div>
            <div className="text-base font-semibold font-mono text-white mb-1">
              GET /health
            </div>
            <p className="text-xs text-alpha-text-secondary">
              Kubernetes liveness heartbeat verifying the event loop is responsive.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-alpha-borderSubtle flex items-center justify-between">
            <span className="text-xs text-alpha-text-muted font-mono">Status:</span>
            <HealthBadge
              status={health?.status === 'healthy' ? 'healthy' : 'degraded'}
              label={health?.status || 'Unknown'}
            />
          </div>
        </div>

        {/* Readiness Probe */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono uppercase text-alpha-text-muted">Readiness Probe</span>
              <Database className="w-4 h-4 text-alpha-gold" />
            </div>
            <div className="text-base font-semibold font-mono text-white mb-1">
              GET /ready
            </div>
            <p className="text-xs text-alpha-text-secondary">
              Verifies TimescaleDB database connectivity and session health.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-alpha-borderSubtle flex items-center justify-between">
            <span className="text-xs text-alpha-text-muted font-mono">Database:</span>
            <HealthBadge
              status={readiness?.components?.database?.connected ? 'healthy' : 'degraded'}
              label={readiness?.components?.database?.connected ? 'Connected' : 'Offline'}
              latencyMs={readiness?.components?.database?.latency_ms}
            />
          </div>
        </div>

        {/* Binance Collector Telemetry */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono uppercase text-alpha-text-muted">Binance Spot Feed</span>
              <Radio className="w-4 h-4 text-alpha-gold" />
            </div>
            <div className="text-base font-semibold font-mono text-white mb-1">
              WebSocket Stream
            </div>
            <p className="text-xs text-alpha-text-secondary">
              Sub-second public kline stream with exponential backoff reconnects.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-alpha-borderSubtle flex items-center justify-between">
            <span className="text-xs text-alpha-text-muted font-mono">Feed State:</span>
            <HealthBadge
              status={marketStatus?.connected ? 'healthy' : 'degraded'}
              label={marketStatus?.feed_state || 'STANDBY'}
            />
          </div>
        </div>
      </div>

      {/* Collector Diagnostics & Reconnection Stats */}
      <div className="p-6 rounded-xl border border-alpha-border bg-alpha-card space-y-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-alpha-gold" />
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
              Market Data Ingestion Telemetry
            </h2>
          </div>
          <span className="text-[11px] font-mono text-alpha-text-muted">BTC/USDT Spot</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle">
            <span className="text-alpha-text-muted block text-[10px] uppercase">Collector Lag</span>
            <p className={`text-xl font-bold mt-1 ${collectorLagSeconds !== null && collectorLagSeconds > 120 ? 'text-rose-400' : 'text-emerald-400'}`}>
              {collectorLagSeconds !== null ? `${collectorLagSeconds}s lag` : 'Standby'}
            </p>
            <span className="text-[10px] text-alpha-text-muted">Threshold: &lt;120s</span>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle">
            <span className="text-alpha-text-muted block text-[10px] uppercase">Reconnect Counts</span>
            <p className="text-xl font-bold text-white mt-1">
              {marketStatus?.reconnect_count ?? 0}
            </p>
            <span className="text-[10px] text-alpha-text-muted">Exponential Backoff</span>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle">
            <span className="text-alpha-text-muted block text-[10px] uppercase">Sequence Gaps</span>
            <p className={`text-xl font-bold mt-1 ${(marketStatus?.gap_count ?? 0) > 0 ? 'text-amber-400' : 'text-white'}`}>
              {marketStatus?.gap_count ?? 0}
            </p>
            <span className="text-[10px] text-alpha-text-muted">Auto REST Backfilled</span>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle">
            <span className="text-alpha-text-muted block text-[10px] uppercase">IP Weight Remaining</span>
            <p className="text-xl font-bold text-alpha-gold mt-1">
              {marketStatus?.rate_limit_remaining ?? 1200}
              <span className="text-xs text-alpha-text-muted font-normal"> / 1200</span>
            </p>
            <span className="text-[10px] text-alpha-text-muted">60s Sliding Window</span>
          </div>
        </div>
      </div>

      {/* Background Orchestration Worker Status */}
      <div className="p-6 rounded-xl border border-alpha-border bg-alpha-card space-y-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-alpha-gold" />
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
              Lifecycle Task Queue & Background Worker
            </h2>
          </div>
          <span className="text-[11px] font-mono text-alpha-text-muted">Single-Worker Invariant</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle">
            <span className="text-alpha-text-muted block text-[10px] uppercase">Worker Status</span>
            <p className="text-base font-bold text-white mt-1">
              {orchestratorStatus?.is_running ? 'RUNNING' : 'IDLE'}
            </p>
            <span className="text-[10px] text-alpha-text-muted">
              Lock Acquired: {orchestratorStatus?.lock_acquired ? 'YES' : 'NO'}
            </span>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle">
            <span className="text-alpha-text-muted block text-[10px] uppercase">Completed Cycles</span>
            <p className="text-xl font-bold text-white mt-1">
              {orchestratorStatus?.cycles_completed ?? 0}
            </p>
            <span className="text-[10px] text-alpha-text-muted">Idempotent Execution</span>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle">
            <span className="text-alpha-text-muted block text-[10px] uppercase">Signals Evaluated</span>
            <p className="text-xl font-bold text-alpha-gold mt-1">
              {orchestratorStatus?.signals_evaluated ?? 0}
            </p>
            <span className="text-[10px] text-alpha-text-muted">Pre-Trade Risk Validated</span>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle">
            <span className="text-alpha-text-muted block text-[10px] uppercase">Simulated Orders</span>
            <p className="text-xl font-bold text-emerald-400 mt-1">
              {orchestratorStatus?.orders_submitted ?? 0}
            </p>
            <span className="text-[10px] text-alpha-text-muted">PaperBroker Submitted</span>
          </div>
        </div>
      </div>

      {/* System Environment & TimescaleDB Telemetry */}
      {systemInfo && (
        <div className="p-6 rounded-xl border border-alpha-border bg-alpha-card space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-alpha-gold" />
              <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
                Environment & Database Telemetry
              </h2>
            </div>
            <span className="text-[11px] font-mono text-alpha-text-muted">
              Uptime: {Math.round(systemInfo.uptime_seconds)}s
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
            <div>
              <span className="text-alpha-text-muted block text-[10px] uppercase">Project Name</span>
              <p className="font-semibold text-white mt-0.5">{systemInfo.project_name}</p>
            </div>
            <div>
              <span className="text-alpha-text-muted block text-[10px] uppercase">Environment</span>
              <p className="font-semibold text-white mt-0.5 uppercase">{systemInfo.environment}</p>
            </div>
            <div>
              <span className="text-alpha-text-muted block text-[10px] uppercase">DB Dialect</span>
              <p className="font-semibold text-white mt-0.5">{systemInfo.database.dialect || 'postgresql'}</p>
            </div>
            <div>
              <span className="text-alpha-text-muted block text-[10px] uppercase">DB Latency</span>
              <p className="font-semibold text-emerald-400 mt-0.5">
                {systemInfo.database.latency_ms !== undefined ? `${systemInfo.database.latency_ms.toFixed(2)} ms` : '—'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Initialization & Diagnostic Logs */}
      <div className="p-6 rounded-xl border border-alpha-border bg-alpha-card space-y-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-alpha-gold" />
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
              System Audit & Initialization Logs ({auditLogs.length})
            </h2>
          </div>
          <span className="text-[11px] font-mono text-alpha-text-muted">Immutable SQLite/PG Records</span>
        </div>

        {auditLogs.length === 0 ? (
          <p className="text-xs font-mono text-alpha-text-muted py-6 text-center">
            No system audit logs recorded.
          </p>
        ) : (
          <div className="overflow-x-auto max-h-80 overflow-y-auto font-mono text-xs">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-alpha-borderSubtle text-alpha-text-muted sticky top-0 bg-alpha-card">
                  <th className="py-2 pr-3">Timestamp (UTC)</th>
                  <th className="py-2 pr-3">Component</th>
                  <th className="py-2 pr-3">Event Type</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-alpha-borderSubtle/60 text-alpha-text-secondary">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-alpha-cardHover transition-colors">
                    <td className="py-2 pr-3 text-alpha-text-muted whitespace-nowrap">
                      {new Date(log.created_at).toISOString().replace('T', ' ').substring(0, 19)}
                    </td>
                    <td className="py-2 pr-3 text-alpha-gold font-semibold whitespace-nowrap">
                      {log.component}
                    </td>
                    <td className="py-2 pr-3 text-white whitespace-nowrap">
                      {log.event_type}
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${
                          log.status === 'success' || log.status === 'ok'
                            ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40'
                            : 'bg-amber-950/40 text-amber-400 border-amber-800/40'
                        }`}
                      >
                        {log.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2 text-[11px] text-alpha-text-secondary">
                      {log.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemHealthPage;
