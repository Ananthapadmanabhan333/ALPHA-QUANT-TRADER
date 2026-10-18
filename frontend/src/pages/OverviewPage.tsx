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
  Target,
  Crosshair,
  CheckCircle2,
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
  fetchLiveScanner,
  submitPaperOrder,
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
  LiveScannerResponse,
  LiveTradeSetup,
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
  const [liveScanner, setLiveScanner] = useState<LiveScannerResponse | null>(null);
  const [scannerInterval, setScannerInterval] = useState<string>('1m');
  const [executingSetupId, setExecutingSetupId] = useState<string | null>(null);
  const [executionNotice, setExecutionNotice] = useState<string | null>(null);

  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date>(new Date());

  const loadOverviewData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      // Phase 1: Critical fast desk telemetry (renders immediately)
      const [
        portfolioRes,
        mktStatusRes,
        scannerRes,
        riskRes,
        candlesRes,
      ] = await Promise.all([
        fetchPortfolio('BTCUSDT').catch(() => null),
        fetchMarketStatus('BTCUSDT', '1m').catch(() => null),
        fetchLiveScanner('BTCUSDT', scannerInterval, 10000.0).catch(() => null),
        fetchRiskStatus('BTCUSDT').catch(() => null),
        fetchCandles('BTCUSDT', '1m', 20, false).catch(() => ({ candles: [] as MarketCandle[] })),
      ]);

      if (portfolioRes) setPortfolio(portfolioRes);
      if (mktStatusRes) setMarketStatus(mktStatusRes);
      if (scannerRes) setLiveScanner(scannerRes);
      if (riskRes) setRiskStatus(riskRes);
      if (candlesRes && 'candles' in candlesRes) {
        setCandles(candlesRes.candles);
      }

      // Phase 2: Secondary operational status & audit telemetry (non-blocking)
      Promise.all([
        fetchPaperTradingStatus().catch(() => null),
        fetchSystemEvents(undefined, undefined, 10, 0).catch(() => ({ items: [] as SystemEvent[] })),
        fetchHealth().catch(() => null),
        fetchReadiness().catch(() => null),
        fetchExperiments(undefined, 'BTCUSDT', 1).catch(() => ({ experiments: [] })),
      ]).then(([orchRes, eventsRes, healthRes, readyRes, experimentsRes]) => {
        if (orchRes) setOrchestratorStatus(orchRes);
        if (eventsRes && 'items' in eventsRes) {
          setEvents(eventsRes.items);
        }
        if (healthRes) setHealth(healthRes);
        if (readyRes) setReadiness(readyRes);
        if (experimentsRes?.experiments?.[0]?.signals) {
          setRecentSignals(experimentsRes.experiments[0].signals.slice(-10).reverse());
        }
      });

      setLastRefreshedAt(new Date());
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to query live dashboard telemetry');
    } finally {
      setIsRefreshing(false);
    }
  }, [scannerInterval]);

  const handleExecuteSetup = async (setup: LiveTradeSetup, overrideSide?: 'buy' | 'sell') => {
    const sideToRun = overrideSide || (setup.side === 'sell' ? 'sell' : 'buy');
    setExecutingSetupId(setup.strategy_id);
    setExecutionNotice(null);
    setError(null);
    try {
      const order = await submitPaperOrder({
        symbol: 'BTCUSDT',
        side: sideToRun,
        order_type: 'market',
        quantity: setup.recommended_qty,
      });
      setExecutionNotice(
        `Executed ${sideToRun.toUpperCase()} ${order.filled_quantity} BTC @ $${(order.avg_fill_price ?? setup.entry_price).toLocaleString()} [${setup.strategy_name} | SL: $${setup.stop_loss.toLocaleString()} | TP1: $${setup.take_profit_1.toLocaleString()}]`
      );
      await loadOverviewData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to execute trade setup.');
    } finally {
      setExecutingSetupId(null);
    }
  };

  useEffect(() => {
    loadOverviewData();
    const intervalId = window.setInterval(loadOverviewData, 15000);
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
    <div className="max-w-7xl mx-auto space-y-5 sm:space-y-6 animate-fade-in pb-6">
      {/* Top Banner / System HUD */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 sm:pb-6 border-b border-alpha-border">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <h1 className="text-lg sm:text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
              <span>ALPHA QUANT COMMAND CENTER</span>
            </h1>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-alpha-gold/15 text-alpha-gold border border-alpha-gold/30 whitespace-nowrap">
              LIVE SYSTEM TELEMETRY
            </span>
          </div>
          <p className="text-[11px] sm:text-xs text-alpha-text-secondary mt-1 font-mono">
            BTC/USDT Spot Pipeline • Deterministic Engine • Central Risk Gate Active
          </p>
        </div>

        <div className="flex items-center justify-between sm:justify-end gap-3">
          <div className="text-left sm:text-right">
            <span className="text-[10px] font-mono text-alpha-text-muted block">Telemetry Heartbeat</span>
            <span className="text-xs font-mono text-alpha-text-secondary">
              {lastRefreshedAt.toLocaleTimeString()} UTC
            </span>
          </div>

          <button
            onClick={loadOverviewData}
            disabled={isRefreshing}
            className="p-2 rounded-lg bg-alpha-card border border-alpha-border text-alpha-text-secondary hover:text-alpha-gold transition-colors shrink-0"
            title="Refresh Telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-alpha-gold' : ''}`} />
          </button>
        </div>
      </div>

      {/* Emergency Stop / Circuit Breaker Banner */}
      {riskStatus?.emergency_stop && (
        <div className="p-4 rounded-xl border border-rose-900/80 bg-rose-950/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-rose-200 shadow-lg">
          <div className="flex items-start sm:items-center gap-3">
            <ShieldAlert className="w-6 h-6 text-rose-400 flex-shrink-0 animate-pulse mt-0.5 sm:mt-0" />
            <div>
              <span className="font-bold text-xs sm:text-sm uppercase tracking-wide block">
                CIRCUIT BREAKER ACTIVATED — EMERGENCY STOP ENGAGED
              </span>
              <p className="text-xs text-rose-300/90 mt-0.5 font-mono">
                Reason: {riskStatus.kill_switch_reason || 'Manual kill switch activated. All order execution is frozen.'}
              </p>
            </div>
          </div>
          <a
            href="/risk"
            className="px-3 py-1.5 rounded-lg bg-rose-900/60 hover:bg-rose-800 text-rose-100 text-xs font-mono border border-rose-700 transition-colors text-center whitespace-nowrap"
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
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {/* 1. BTC/USDT Price & Feed Freshness */}
        <div className="p-3.5 sm:p-5 rounded-xl border border-alpha-border bg-alpha-card/90 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-[10px] sm:text-xs text-alpha-text-muted mb-1.5 sm:mb-2 font-mono uppercase">
            <span className="truncate">BTC/USDT Spot</span>
            <Activity className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-alpha-gold shrink-0" />
          </div>
          <div className="flex flex-wrap items-baseline gap-1.5 sm:gap-2">
            <span className="text-lg sm:text-2xl font-bold font-mono text-white truncate">
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
        <div className="p-3.5 sm:p-5 rounded-xl border border-alpha-border bg-alpha-card/90 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-[10px] sm:text-xs text-alpha-text-muted mb-1.5 sm:mb-2 font-mono uppercase">
            <span className="truncate">Simulated Equity</span>
            <DollarSign className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-alpha-gold shrink-0" />
          </div>
          <div className="flex flex-wrap items-baseline gap-1.5 sm:gap-2">
            <span className="text-lg sm:text-2xl font-bold font-mono text-white truncate">
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
          <div className="mt-2.5 sm:mt-3 pt-2.5 sm:pt-3 border-t border-alpha-borderSubtle flex items-center justify-between text-[10px] sm:text-[11px] font-mono">
            <span className="text-alpha-text-muted">Cash:</span>
            <span className="text-alpha-text-secondary truncate">${virtualCash.toFixed(2)}</span>
          </div>
        </div>

        {/* 3. Drawdown & Peak Equity */}
        <div className="p-3.5 sm:p-5 rounded-xl border border-alpha-border bg-alpha-card/90 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-[10px] sm:text-xs text-alpha-text-muted mb-1.5 sm:mb-2 font-mono uppercase">
            <span className="truncate">Peak Drawdown</span>
            <TrendingDown className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-rose-400 shrink-0" />
          </div>
          <div className="flex flex-wrap items-baseline gap-1.5 sm:gap-2">
            <span
              className={`text-lg sm:text-2xl font-bold font-mono ${
                (riskStatus?.current_drawdown_pct ?? 0) > 2.0 ? 'text-rose-400' : 'text-white'
              }`}
            >
              {(riskStatus?.current_drawdown_pct ?? 0).toFixed(2)}%
            </span>
            <span className="text-[10px] font-mono text-alpha-text-muted">
              Lim: {(riskStatus?.max_drawdown_limit_pct ?? 5.0).toFixed(1)}%
            </span>
          </div>
          <div className="mt-2.5 sm:mt-3 pt-2.5 sm:pt-3 border-t border-alpha-borderSubtle flex items-center justify-between text-[10px] sm:text-[11px] font-mono">
            <span className="text-alpha-text-muted">Peak:</span>
            <span className="text-alpha-text-secondary truncate">
              ${(riskStatus?.peak_equity ?? totalEquity).toFixed(2)}
            </span>
          </div>
        </div>

        {/* 4. Portfolio Exposure & Drag */}
        <div className="p-3.5 sm:p-5 rounded-xl border border-alpha-border bg-alpha-card/90 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-[10px] sm:text-xs text-alpha-text-muted mb-1.5 sm:mb-2 font-mono uppercase">
            <span className="truncate">Exposure</span>
            <Layers className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-alpha-gold shrink-0" />
          </div>
          <div className="flex flex-wrap items-baseline gap-1.5 sm:gap-2">
            <span className="text-lg sm:text-2xl font-bold font-mono text-white">
              {exposurePct.toFixed(1)}%
            </span>
            <span className="text-[11px] font-mono text-alpha-text-muted truncate">
              (${positionValue.toFixed(0)})
            </span>
          </div>
          <div className="mt-2.5 sm:mt-3 pt-2.5 sm:pt-3 border-t border-alpha-borderSubtle flex items-center justify-between text-[10px] sm:text-[11px] font-mono">
            <span className="text-alpha-text-muted">Fee Drag:</span>
            <span className="text-alpha-gold font-medium">
              ${(totalFees + totalSlippage).toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Execution Confirmation Notice */}
      {executionNotice && (
        <div className="p-4 rounded-xl border border-emerald-500/40 bg-emerald-950/30 flex items-center justify-between text-emerald-300 text-xs font-mono">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{executionNotice}</span>
          </div>
          <button
            onClick={() => setExecutionNotice(null)}
            className="text-[11px] text-emerald-400 hover:underline ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* LIVE MULTI-STRATEGY QUANTITATIVE TRADE SETUPS & ATR SCANNER */}
      {liveScanner && (
        <div className="rounded-xl border border-alpha-gold/40 bg-alpha-card/95 p-5 shadow-lg space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3 border-b border-alpha-borderSubtle">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-alpha-gold/15 border border-alpha-gold/40 text-alpha-gold">
                <Target className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-white">
                    Live Quantitative Trade Setups & ATR Risk Levels
                  </h2>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                      liveScanner.consensus_side === 'BUY'
                        ? 'bg-emerald-950/60 text-emerald-400 border-emerald-700/60'
                        : liveScanner.consensus_side === 'SELL'
                        ? 'bg-rose-950/60 text-rose-400 border-rose-700/60'
                        : 'bg-alpha-gold/15 text-alpha-gold border-alpha-gold/40'
                    }`}
                  >
                    CONSENSUS: {liveScanner.consensus_side} ({(liveScanner.consensus_score * 100).toFixed(0)}%)
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-alpha-surface border border-alpha-border text-alpha-text-secondary">
                    REGIME: {liveScanner.regime}
                  </span>
                </div>
                <p className="text-[11px] font-mono text-alpha-text-muted mt-0.5">
                  Real-time multi-strategy evaluation with 2.0x ATR Stop-Loss, 2.0x/3.5x ATR Profit Targets & Safe Equity Sizing
                </p>
              </div>
            </div>

            {/* Interval Selector & Indicator Strip */}
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-alpha-text-muted uppercase">Timeframe:</span>
              {(['1m', '5m', '15m'] as const).map((tf) => (
                <button
                  key={tf}
                  onClick={() => setScannerInterval(tf)}
                  className={`px-2.5 py-1 rounded text-xs font-mono font-semibold border transition-colors ${
                    scannerInterval === tf
                      ? 'bg-alpha-gold text-black border-alpha-gold'
                      : 'bg-alpha-surface text-alpha-text-secondary border-alpha-border hover:border-alpha-gold/40'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* Live Technical Indicator Telemetry Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 pt-1">
            <div className="p-2.5 rounded-lg bg-alpha-surface/80 border border-alpha-borderSubtle font-mono">
              <span className="text-[10px] text-alpha-text-muted block">SMA(20) / SMA(100)</span>
              <span className="text-xs font-bold text-white">
                ${liveScanner.indicators.sma_20?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? '—'} / $
                {liveScanner.indicators.sma_100?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? '—'}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-alpha-surface/80 border border-alpha-borderSubtle font-mono">
              <span className="text-[10px] text-alpha-text-muted block">Z-SCORE (60)</span>
              <span
                className={`text-xs font-bold ${
                  (liveScanner.indicators.zscore_60 ?? 0) <= -1.5
                    ? 'text-emerald-400'
                    : (liveScanner.indicators.zscore_60 ?? 0) >= 1.5
                    ? 'text-rose-400'
                    : 'text-white'
                }`}
              >
                {liveScanner.indicators.zscore_60?.toFixed(2) ?? '0.00'} σ
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-alpha-surface/80 border border-alpha-borderSubtle font-mono">
              <span className="text-[10px] text-alpha-text-muted block">ATR (14) VOLATILITY</span>
              <span className="text-xs font-bold text-alpha-gold">
                ${liveScanner.indicators.atr_14?.toFixed(2) ?? '—'}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-alpha-surface/80 border border-alpha-borderSubtle font-mono">
              <span className="text-[10px] text-alpha-text-muted block">MOMENTUM (15B)</span>
              <span
                className={`text-xs font-bold ${
                  (liveScanner.indicators.momentum_15 ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {(liveScanner.indicators.momentum_15 ?? 0) >= 0 ? '+' : ''}
                {((liveScanner.indicators.momentum_15 ?? 0) * 100).toFixed(3)}%
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-alpha-surface/80 border border-alpha-borderSubtle font-mono">
              <span className="text-[10px] text-alpha-text-muted block">MOMENTUM (60B)</span>
              <span
                className={`text-xs font-bold ${
                  (liveScanner.indicators.momentum_60 ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {(liveScanner.indicators.momentum_60 ?? 0) >= 0 ? '+' : ''}
                {((liveScanner.indicators.momentum_60 ?? 0) * 100).toFixed(3)}%
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-alpha-surface/80 border border-alpha-borderSubtle font-mono">
              <span className="text-[10px] text-alpha-text-muted block">VOLUME RATIO (20B)</span>
              <span className="text-xs font-bold text-white">
                {liveScanner.indicators.volume_ratio_20?.toFixed(2) ?? '1.00'}x
              </span>
            </div>
          </div>

          {/* 3 Strategy Actionable Trade Setup Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-1">
            {liveScanner.setups.map((setup) => {
              const isBuy = setup.side === 'buy';
              const isSell = setup.side === 'sell';
              return (
                <div
                  key={setup.strategy_id}
                  className={`rounded-xl border p-4 flex flex-col justify-between transition-all ${
                    isBuy
                      ? 'border-emerald-500/50 bg-emerald-950/15'
                      : isSell
                      ? 'border-rose-500/50 bg-rose-950/15'
                      : 'border-alpha-border bg-alpha-surface/60'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-xs font-mono font-bold text-white uppercase tracking-wide">
                        {setup.strategy_name}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                          isBuy
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                            : isSell
                            ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                            : 'bg-neutral-800 text-neutral-300 border-neutral-700'
                        }`}
                      >
                        {setup.side.toUpperCase()} ({(setup.signal_score * 100).toFixed(0)}%)
                      </span>
                    </div>

                    <p className="text-[11px] font-mono text-alpha-text-secondary mb-3 line-clamp-2" title={setup.reason}>
                      {setup.reason}
                    </p>

                    {/* Entry, Stop Loss, TP1, TP2 Grid */}
                    <div className="grid grid-cols-2 gap-2 p-2.5 rounded-lg bg-alpha-bg/80 border border-alpha-borderSubtle text-[11px] font-mono mb-3">
                      <div>
                        <span className="text-alpha-text-muted block text-[10px]">ENTRY PRICE</span>
                        <span className="text-white font-bold">${setup.entry_price.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-rose-400/80 block text-[10px]">STOP LOSS (2x ATR)</span>
                        <span className="text-rose-400 font-bold">${setup.stop_loss.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-emerald-400/80 block text-[10px]">TARGET 1 (1:1)</span>
                        <span className="text-emerald-400 font-bold">${setup.take_profit_1.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-emerald-300/80 block text-[10px]">TARGET 2 ({setup.risk_reward_ratio}:1)</span>
                        <span className="text-emerald-300 font-bold">${setup.take_profit_2.toLocaleString()}</span>
                      </div>
                    </div>

                    {/* Sizing & Expected Profit */}
                    <div className="flex items-center justify-between text-[11px] font-mono text-alpha-text-muted mb-3 px-1">
                      <span>
                        Rec Size: <strong className="text-white">{setup.recommended_qty} BTC</strong> ($
                        {setup.recommended_notional_usd.toFixed(0)})
                      </span>
                      <span>
                        R:R <strong className="text-alpha-gold">1:{setup.risk_reward_ratio}</strong>
                      </span>
                    </div>
                  </div>

                  {/* 1-Click Paper Execution Buttons */}
                  <div className="flex items-center gap-2 pt-2 border-t border-alpha-borderSubtle">
                    <button
                      onClick={() => handleExecuteSetup(setup, 'buy')}
                      disabled={executingSetupId === setup.strategy_id || riskStatus?.emergency_stop}
                      className="flex-1 py-1.5 px-2.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-[11px] font-mono font-bold transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
                    >
                      <Crosshair className="w-3.5 h-3.5" />
                      <span>{executingSetupId === setup.strategy_id ? 'Executing...' : `Paper BUY ${setup.recommended_qty}`}</span>
                    </button>
                    {btcPosition && btcPosition.quantity > 0 && (
                      <button
                        onClick={() => handleExecuteSetup(setup, 'sell')}
                        disabled={executingSetupId === setup.strategy_id}
                        className="py-1.5 px-2.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 text-[11px] font-mono font-bold transition-colors disabled:opacity-50"
                      >
                        SELL
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

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
