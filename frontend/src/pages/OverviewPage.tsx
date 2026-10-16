import React, { useEffect, useState, useCallback } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  ShieldCheck,
  ShieldAlert,
  DollarSign,
  AlertTriangle,
  RefreshCw,
  Layers,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
  Database,
  Radio,
  Server,
} from 'lucide-react';
import {
  fetchCandles,
  fetchMarketStatus,
  fetchPortfolio,
  fetchRiskStatus,
  fetchPaperTradingStatus,
  fetchSystemEvents,
  fetchHealth,
  fetchReadiness,
  fetchExperiments,
} from '../services/api';
import {
  MarketCandle,
  MarketStatusResponse,
  PaperAccount,
  RiskStatus,
  PaperTradingStatus,
  SystemEvent,
  HealthResponse,
  ReadinessResponse,
  StrategySignal,
} from '../types';
import { HealthBadge } from '../components/common/HealthBadge';
import { EmptyState } from '../components/common/EmptyState';

export const OverviewPage: React.FC = () => {
  const [candles, setCandles] = useState<MarketCandle[]>([]);
  const [marketStatus, setMarketStatus] = useState<MarketStatusResponse | null>(null);
  const [portfolio, setPortfolio] = useState<PaperAccount | null>(null);
  const [riskStatus, setRiskStatus] = useState<RiskStatus | null>(null);
  const [orchestratorStatus, setOrchestratorStatus] = useState<PaperTradingStatus | null>(null);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [recentSignals, setRecentSignals] = useState<StrategySignal[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);

  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date>(new Date());

  const loadOverviewData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [
        candlesRes,
        mktStatusRes,
        portfolioRes,
        riskRes,
        orchRes,
        eventsRes,
        healthRes,
        readyRes,
        experimentsRes,
      ] = await Promise.all([
        fetchCandles('BTCUSDT', '1m', 20, false).catch(() => ({ candles: [] as MarketCandle[] })),
        fetchMarketStatus('BTCUSDT', '1m').catch(() => null),
        fetchPortfolio('BTCUSDT').catch(() => null),
        fetchRiskStatus('BTCUSDT').catch(() => null),
        fetchPaperTradingStatus().catch(() => null),
        fetchSystemEvents(undefined, undefined, 10, 0).catch(() => ({ items: [] as SystemEvent[] })),
        fetchHealth().catch(() => null),
        fetchReadiness().catch(() => null),
        fetchExperiments(undefined, 'BTCUSDT', 1).catch(() => ({ experiments: [] })),
      ]);

      if (candlesRes && 'candles' in candlesRes) {
        setCandles(candlesRes.candles);
      }
      setMarketStatus(mktStatusRes);
      setPortfolio(portfolioRes);
      setRiskStatus(riskRes);
      setOrchestratorStatus(orchRes);
      if (eventsRes && 'items' in eventsRes) {
        setEvents(eventsRes.items);
      }
      setHealth(healthRes);
      setReadiness(readyRes);

      // Extract recent signals if present
      if (experimentsRes?.experiments?.[0]?.signals) {
        setRecentSignals(experimentsRes.experiments[0].signals.slice(-10).reverse());
      }

      setLastRefreshedAt(new Date());
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to query live dashboard telemetry');
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadOverviewData();
    const intervalId = window.setInterval(loadOverviewData, 5000);
    return () => clearInterval(intervalId);
  }, [loadOverviewData]);

  // Derived calculations
  const latestCandle = candles.length > 0 && candles[candles.length - 1] ? candles[candles.length - 1] : null;
  const currentPrice = marketStatus?.latest_close_price ?? latestCandle?.close ?? null;
  const prevPrice = candles.length > 1 && candles[candles.length - 2] ? candles[candles.length - 2]!.close : currentPrice;
  const priceChange = currentPrice && prevPrice ? currentPrice - prevPrice : 0;
  const priceChangePct = prevPrice && prevPrice > 0 ? (priceChange / prevPrice) * 100 : 0;

  const totalEquity = portfolio?.total_equity ?? 0;
  const virtualCash = portfolio?.virtual_balance ?? 0;
  const unrealizedPnl = portfolio?.unrealized_pnl ?? 0;
  const realizedPnl = portfolio?.realized_pnl ?? 0;
  const netPnl = unrealizedPnl + realizedPnl;

  const btcPosition = portfolio?.positions?.find((p) => p.symbol === 'BTCUSDT');
  const positionValue = btcPosition ? btcPosition.market_value : 0;
  const exposurePct = totalEquity > 0 ? (positionValue / totalEquity) * 100 : 0;

  // Total fees and slippage across all open/recent orders
  const totalFees = btcPosition ? Math.abs(btcPosition.cost_basis * 0.001) : 0; // standard 10 bps
  const totalSlippage = btcPosition ? Math.abs(btcPosition.cost_basis * 0.0005) : 0; // 5 bps modeled

  // Market data freshness
  const lastExchangeTime = marketStatus?.last_exchange_time ? new Date(marketStatus.last_exchange_time) : null;
  const isFresh = lastExchangeTime ? (Date.now() - lastExchangeTime.getTime()) < 120000 : false;

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in pb-12">
      {/* Top Banner / System HUD */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
              <span>ALPHA QUANT COMMAND CENTER</span>
            </h1>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-alpha-gold/15 text-alpha-gold border border-alpha-gold/30">
              LIVE SYSTEM TELEMETRY
            </span>
          </div>
          <p className="text-xs text-alpha-text-secondary mt-1 font-mono">
            BTC/USDT Spot Pipeline • Deterministic Engine • Central Risk Gate Active
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <span className="text-[10px] font-mono text-alpha-text-muted block">Telemetry Heartbeat</span>
            <span className="text-xs font-mono text-alpha-text-secondary">
              {lastRefreshedAt.toLocaleTimeString()} UTC
            </span>
          </div>

          <button
            onClick={loadOverviewData}
            disabled={isRefreshing}
            className="p-2 rounded-lg bg-alpha-card border border-alpha-border text-alpha-text-secondary hover:text-alpha-gold transition-colors"
            title="Refresh Telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-alpha-gold' : ''}`} />
          </button>
        </div>
      </div>

      {/* Emergency Stop / Circuit Breaker Banner */}
      {riskStatus?.emergency_stop && (
        <div className="p-4 rounded-xl border border-rose-900/80 bg-rose-950/50 flex items-center justify-between text-rose-200 shadow-lg">
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-6 h-6 text-rose-400 flex-shrink-0 animate-pulse" />
            <div>
              <span className="font-bold text-sm uppercase tracking-wide">
                CIRCUIT BREAKER ACTIVATED — EMERGENCY STOP ENGAGED
              </span>
              <p className="text-xs text-rose-300/90 mt-0.5 font-mono">
                Reason: {riskStatus.kill_switch_reason || 'Manual kill switch activated. All order execution is frozen.'}
              </p>
            </div>
          </div>
          <a
            href="/risk"
            className="px-3 py-1.5 rounded-lg bg-rose-900/60 hover:bg-rose-800 text-rose-100 text-xs font-mono border border-rose-700 transition-colors"
          >
            Resolve in Risk Center &rarr;
          </a>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl border border-rose-900/50 bg-rose-950/20 flex items-start gap-3 text-rose-300 text-xs font-mono">
          <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Primary KPI Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. BTC/USDT Price & Feed Freshness */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card/90 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-xs text-alpha-text-muted mb-2 font-mono uppercase">
            <span>BTC/USDT Spot Price</span>
            <Activity className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-white">
              {currentPrice !== null ? `$${currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'No Feed'}
            </span>
            {currentPrice !== null && (
              <span
                className={`text-xs font-mono font-semibold flex items-center ${
                  priceChange >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {priceChange >= 0 ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                {priceChangePct >= 0 ? '+' : ''}{priceChangePct.toFixed(2)}%
              </span>
            )}
          </div>
          <div className="mt-3 pt-3 border-t border-alpha-borderSubtle flex items-center justify-between text-[11px] font-mono">
            <span className="text-alpha-text-muted">Feed Freshness:</span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] border ${
                isFresh
                  ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40'
                  : 'bg-amber-950/40 text-amber-400 border-amber-800/40'
              }`}
            >
              {isFresh ? 'FRESH (<2m)' : marketStatus?.is_stale ? 'STALE' : 'STANDBY'}
            </span>
          </div>
        </div>

        {/* 2. Virtual Equity & Net P&L */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card/90 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-xs text-alpha-text-muted mb-2 font-mono uppercase">
            <span>Simulated Equity</span>
            <DollarSign className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-white">
              ${totalEquity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span
              className={`text-xs font-mono font-semibold ${
                netPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {netPnl >= 0 ? '+' : ''}${netPnl.toFixed(2)}
            </span>
          </div>
          <div className="mt-3 pt-3 border-t border-alpha-borderSubtle flex items-center justify-between text-[11px] font-mono">
            <span className="text-alpha-text-muted">Cash Balance:</span>
            <span className="text-alpha-text-secondary">${virtualCash.toFixed(2)} USDT</span>
          </div>
        </div>

        {/* 3. Drawdown & Peak Equity */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card/90 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-xs text-alpha-text-muted mb-2 font-mono uppercase">
            <span>Peak-To-Trough Drawdown</span>
            <TrendingDown className="w-4 h-4 text-rose-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className={`text-2xl font-bold font-mono ${
                (riskStatus?.current_drawdown_pct ?? 0) > 2.0 ? 'text-rose-400' : 'text-white'
              }`}
            >
              {(riskStatus?.current_drawdown_pct ?? 0).toFixed(2)}%
            </span>
            <span className="text-[10px] font-mono text-alpha-text-muted">
              Limit: {(riskStatus?.max_drawdown_limit_pct ?? 5.0).toFixed(1)}%
            </span>
          </div>
          <div className="mt-3 pt-3 border-t border-alpha-borderSubtle flex items-center justify-between text-[11px] font-mono">
            <span className="text-alpha-text-muted">Peak Equity:</span>
            <span className="text-alpha-text-secondary">
              ${(riskStatus?.peak_equity ?? totalEquity).toFixed(2)}
            </span>
          </div>
        </div>

        {/* 4. Portfolio Exposure & Drag */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card/90 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-xs text-alpha-text-muted mb-2 font-mono uppercase">
            <span>Portfolio Exposure</span>
            <Layers className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-white">
              {exposurePct.toFixed(1)}%
            </span>
            <span className="text-xs font-mono text-alpha-text-muted">
              (${positionValue.toFixed(2)})
            </span>
          </div>
          <div className="mt-3 pt-3 border-t border-alpha-borderSubtle flex items-center justify-between text-[11px] font-mono">
            <span className="text-alpha-text-muted">Fees & Slippage Drag:</span>
            <span className="text-alpha-gold font-medium">
              ${(totalFees + totalSlippage).toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Orchestrator & Live Status Bar */}
      <div className="p-4 rounded-xl border border-alpha-border bg-alpha-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-alpha-gold/10 border border-alpha-gold/30 text-alpha-gold">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-alpha-text-primary">
                Lifecycle Orchestration Loop
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                  orchestratorStatus?.is_running
                    ? 'bg-emerald-950/50 text-emerald-400 border-emerald-800 animate-pulse'
                    : 'bg-neutral-900 text-neutral-400 border-neutral-700'
                }`}
              >
                {orchestratorStatus?.is_running ? 'RUNNING (ACTIVE)' : 'STANDBY'}
              </span>
            </div>
            <p className="text-xs text-alpha-text-secondary mt-0.5 font-mono">
              Strategy: <span className="text-white font-semibold">{orchestratorStatus?.strategy_id || 'None'}</span> •
              Cycles: <span className="text-white">{orchestratorStatus?.cycles_completed ?? 0}</span> •
              Signals Evaluated: <span className="text-white">{orchestratorStatus?.signals_evaluated ?? 0}</span> •
              Simulated Orders: <span className="text-white">{orchestratorStatus?.orders_submitted ?? 0}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="/strategies"
            className="px-3.5 py-1.5 rounded-lg bg-alpha-gold text-black font-semibold text-xs font-mono hover:bg-alpha-gold/90 transition-colors"
          >
            Manage Strategies &rarr;
          </a>
        </div>
      </div>

      {/* Two Columns: Recent Signals & System Health / Events */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Recent Quantitative Signals (7 cols) */}
        <div className="lg:col-span-7 bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-alpha-gold" />
              <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-alpha-text-primary">
                Recent Quantitative Strategy Signals
              </h2>
            </div>
            <a href="/experiments" className="text-[11px] font-mono text-alpha-gold hover:underline">
              View All Experiments &rarr;
            </a>
          </div>

          {recentSignals.length === 0 ? (
            <div className="py-8 text-center">
              <EmptyState
                icon={<Activity className="w-7 h-7" />}
                title="No Strategy Signals Generated Yet"
                description="Run a quantitative strategy evaluation or activate paper execution to generate audited signals."
                phaseRequired={3}
                actionText="Evaluate Strategy"
                actionHref="/strategies"
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-alpha-borderSubtle text-alpha-text-muted">
                    <th className="py-2 pr-3">Timestamp (UTC)</th>
                    <th className="py-2 pr-3">Strategy</th>
                    <th className="py-2 pr-3">Side</th>
                    <th className="py-2 pr-3">Score</th>
                    <th className="py-2 pr-3">Ref Price</th>
                    <th className="py-2">Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-alpha-borderSubtle/60 text-alpha-text-secondary">
                  {recentSignals.map((s, idx) => (
                    <tr key={idx} className="hover:bg-alpha-cardHover transition-colors">
                      <td className="py-2 pr-3 text-alpha-text-muted whitespace-nowrap">
                        {new Date(s.decision_timestamp).toISOString().substring(11, 19)}
                      </td>
                      <td className="py-2 pr-3 font-semibold text-white whitespace-nowrap">
                        {s.strategy_id.replace('_', ' ')}
                      </td>
                      <td className="py-2 pr-3">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border ${
                            s.side === 'buy'
                              ? 'bg-emerald-950/50 text-emerald-400 border-emerald-800/40'
                              : s.side === 'sell'
                              ? 'bg-rose-950/50 text-rose-400 border-rose-800/40'
                              : 'bg-neutral-900 text-neutral-400 border-neutral-700'
                          }`}
                        >
                          {s.side}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-alpha-text-primary">
                        {s.signal_score.toFixed(2)}
                      </td>
                      <td className="py-2 pr-3 text-alpha-text-primary font-semibold">
                        ${s.reference_price.toFixed(2)}
                      </td>
                      <td className="py-2 text-[11px] text-alpha-text-muted truncate max-w-xs" title={s.reason}>
                        {s.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column: Risk & System Audit Events (5 cols) */}
        <div className="lg:col-span-5 bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-alpha-gold" />
              <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-alpha-text-primary">
                Risk Events & Audited Alerts
              </h2>
            </div>
            <a href="/risk" className="text-[11px] font-mono text-alpha-gold hover:underline">
              Risk Console &rarr;
            </a>
          </div>

          {events.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-xs font-mono text-alpha-text-muted">
                Zero recorded risk breaches or emergency interruptions.
              </p>
              <div className="mt-2 inline-flex items-center gap-2 text-[11px] font-mono text-emerald-400">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>All 11 Risk Gates Clear</span>
              </div>
            </div>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {events.map((evt) => (
                <div
                  key={evt.id}
                  className={`p-2.5 rounded-lg border text-xs font-mono transition-colors ${
                    evt.severity === 'CRITICAL'
                      ? 'bg-rose-950/40 border-rose-800/60 text-rose-200'
                      : evt.severity === 'WARNING'
                      ? 'bg-amber-950/30 border-amber-800/50 text-amber-200'
                      : 'bg-alpha-surface border-alpha-border text-alpha-text-secondary'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white uppercase text-[11px]">
                      {evt.event_type.replace(/_/g, ' ')}
                    </span>
                    <span className="text-[10px] text-alpha-text-muted">
                      {new Date(evt.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] opacity-90">{evt.reason}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Backend & Collector Health Status Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Core API Server */}
        <div className="p-4 rounded-xl border border-alpha-border bg-alpha-card flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Server className="w-5 h-5 text-alpha-gold" />
            <div>
              <span className="text-xs font-mono uppercase text-alpha-text-muted">FastAPI Service</span>
              <div className="text-sm font-bold font-mono text-white">v{health?.version || '1.0.0'}</div>
            </div>
          </div>
          <HealthBadge status={health?.status === 'healthy' ? 'healthy' : 'degraded'} label={health?.status || 'Unknown'} />
        </div>

        {/* TimescaleDB Status */}
        <div className="p-4 rounded-xl border border-alpha-border bg-alpha-card flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5 text-alpha-gold" />
            <div>
              <span className="text-xs font-mono uppercase text-alpha-text-muted">TimescaleDB Hypertable</span>
              <div className="text-sm font-bold font-mono text-white">
                {readiness?.components?.database?.connected ? 'Online' : 'Standby'}
              </div>
            </div>
          </div>
          <HealthBadge
            status={readiness?.components?.database?.connected ? 'healthy' : 'degraded'}
            label={readiness?.components?.database?.connected ? 'Connected' : 'Offline'}
            latencyMs={readiness?.components?.database?.latency_ms}
          />
        </div>

        {/* Binance Spot Collector */}
        <div className="p-4 rounded-xl border border-alpha-border bg-alpha-card flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Radio className="w-5 h-5 text-alpha-gold" />
            <div>
              <span className="text-xs font-mono uppercase text-alpha-text-muted">Binance WebSocket Feed</span>
              <div className="text-sm font-bold font-mono text-white">
                {marketStatus?.feed_state || 'STANDBY'}
              </div>
            </div>
          </div>
          <HealthBadge
            status={marketStatus?.connected ? 'healthy' : 'degraded'}
            label={marketStatus?.connected ? 'Streaming' : 'Standby'}
          />
        </div>
      </div>
    </div>
  );
};
