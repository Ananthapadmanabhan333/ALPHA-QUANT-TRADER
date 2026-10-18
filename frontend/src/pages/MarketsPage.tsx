import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  TrendingUp,
  RefreshCw,
  Database,
  AlertTriangle,
  Radio,
} from 'lucide-react';
import {
  fetchCandles,
  fetchMarketStatus,
  fetchExperiments,
  fetchExperimentDetails,
  triggerMarketBackfill,
} from '../services/api';
import { MarketCandle, MarketStatusResponse, StrategySignal } from '../types';
import { EmptyState } from '../components/common/EmptyState';

// Helper to calculate simple moving average
function calculateSMA(data: number[], window: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < window - 1) {
      result.push(null);
    } else {
      const slice = data.slice(i - window + 1, i + 1);
      const sum = slice.reduce((acc, v) => acc + v, 0);
      result.push(sum / window);
    }
  }
  return result;
}

export const MarketsPage: React.FC = () => {
  const [interval, setInterval] = useState<'1m' | '5m' | '15m'>('1m');
  const [symbol] = useState<string>('BTCUSDT');
  const [limit, setLimit] = useState<number>(100);
  const [candles, setCandles] = useState<MarketCandle[]>([]);
  const [status, setStatus] = useState<MarketStatusResponse | null>(null);
  const [signals, setSignals] = useState<StrategySignal[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Overlay toggles
  const [showSMA20, setShowSMA20] = useState<boolean>(true);
  const [showSMA100, setShowSMA100] = useState<boolean>(true);
  const [showSignals, setShowSignals] = useState<boolean>(true);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [candlesRes, statusRes, expRes] = await Promise.all([
        fetchCandles(symbol, interval, limit, false).catch(() => ({
          symbol,
          interval,
          count: 0,
          only_closed: false,
          candles: [],
        })),
        fetchMarketStatus(symbol, interval).catch(() => null),
        fetchExperiments(undefined, symbol, 1).catch(() => ({ experiments: [] })),
      ]);

      // Candles from API come oldest first or newest first?
      // In backend, candles are sorted ASC by open_time
      setCandles(candlesRes.candles);
      setStatus(statusRes);

      const firstExp = expRes.experiments?.[0];
      if (firstExp) {
        if (firstExp.signals && firstExp.signals.length > 0) {
          setSignals(firstExp.signals);
        } else {
          const detailed = await fetchExperimentDetails(firstExp.id).catch(() => null);
          if (detailed?.signals) {
            setSignals(detailed.signals);
          }
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to query market data');
    } finally {
      setLoading(false);
    }
  }, [symbol, interval, limit]);

  const handleSyncExchange = async () => {
    setSyncing(true);
    setSyncMsg(null);
    setError(null);
    try {
      const hoursBack = interval === '1m' ? 6 : interval === '5m' ? 24 : 72;
      const start = new Date(Date.now() - hoursBack * 3600 * 1000).toISOString();
      const res = await triggerMarketBackfill(symbol, interval, start);
      setSyncMsg(`Synced ${res.candles_saved} ${interval} candles from Binance Spot (${res.duration_ms.toFixed(0)}ms)`);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to sync from Binance exchange');
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = window.setInterval(loadData, 5000);
    return () => clearInterval(timer);
  }, [loadData]);

  // Compute overlays
  const closePrices = useMemo(() => candles.map((c) => c.close), [candles]);
  const sma20 = useMemo(() => calculateSMA(closePrices, 20), [closePrices]);
  const sma100 = useMemo(() => calculateSMA(closePrices, 100), [closePrices]);

  // Map signals to candle timestamps for easy lookup
  const signalMap = useMemo(() => {
    const map = new Map<string, StrategySignal>();
    for (const sig of signals) {
      map.set(sig.decision_timestamp, sig);
    }
    return map;
  }, [signals]);

  // SVG Chart Dimensions & Calculations
  const chartHeight = 360;
  const volumeHeight = 80;
  const totalSvgHeight = chartHeight + volumeHeight + 40;
  const paddingLeft = 55;
  const paddingRight = 30;
  const paddingTop = 20;

  const minPrice = useMemo(() => {
    if (candles.length === 0) return 0;
    return Math.min(...candles.map((c) => c.low)) * 0.999;
  }, [candles]);

  const maxPrice = useMemo(() => {
    if (candles.length === 0) return 100;
    return Math.max(...candles.map((c) => c.high)) * 1.001;
  }, [candles]);

  const maxVolume = useMemo(() => {
    if (candles.length === 0) return 1;
    return Math.max(...candles.map((c) => c.volume)) * 1.05;
  }, [candles]);

  const getY = (price: number) => {
    if (maxPrice === minPrice) return chartHeight / 2;
    return chartHeight - ((price - minPrice) / (maxPrice - minPrice)) * (chartHeight - paddingTop) + paddingTop;
  };

  const getVolY = (vol: number) => {
    if (maxVolume === 0) return chartHeight + volumeHeight;
    return chartHeight + volumeHeight - (vol / maxVolume) * (volumeHeight - 10);
  };

  const hoveredCandle = hoveredIndex !== null && candles[hoveredIndex] ? candles[hoveredIndex] : null;

  return (
    <div className="max-w-7xl mx-auto space-y-5 sm:space-y-6 animate-fade-in pb-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 pb-4 sm:pb-6 border-b border-alpha-border">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <h1 className="text-lg sm:text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
              <TrendingUp className="w-5 h-5 sm:w-6 sm:h-6 text-alpha-gold shrink-0" />
              <span>MARKET DATA & OVERLAYS</span>
            </h1>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-alpha-gold/10 text-alpha-gold border border-alpha-gold/30 whitespace-nowrap">
              BTC/USDT SPOT
            </span>
          </div>
          <p className="text-[11px] sm:text-xs text-alpha-text-secondary mt-1 font-mono">
            Binance Public Spot Feed • Sub-second Ingestion • Continuous Partitioning
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          {/* Interval Selector */}
          <div className="flex items-center bg-alpha-card rounded-lg p-1 border border-alpha-border">
            {(['1m', '5m', '15m'] as const).map((int) => (
              <button
                key={int}
                onClick={() => setInterval(int)}
                className={`px-2.5 sm:px-3 py-1 text-xs font-mono rounded font-medium transition-colors ${
                  interval === int
                    ? 'bg-alpha-gold text-black font-semibold shadow-sm'
                    : 'text-alpha-text-secondary hover:text-white'
                }`}
              >
                {int}
              </button>
            ))}
          </div>

          {/* Candle Count Selector */}
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="bg-alpha-card border border-alpha-border text-xs font-mono text-alpha-text-secondary rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-alpha-gold"
          >
            <option value={50}>50 Bars</option>
            <option value={100}>100 Bars</option>
            <option value={200}>200 Bars</option>
            <option value={300}>300 Bars</option>
          </select>

          <button
            onClick={handleSyncExchange}
            disabled={syncing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-semibold rounded-lg bg-alpha-gold/15 text-alpha-gold border border-alpha-gold/40 hover:bg-alpha-gold/25 transition-colors disabled:opacity-50"
            title="Sync latest candles directly from Binance Spot REST API"
          >
            <Radio className={`w-3.5 h-3.5 ${syncing ? 'animate-pulse' : ''}`} />
            <span>{syncing ? 'Syncing...' : 'Sync Exchange'}</span>
          </button>

          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-lg bg-alpha-card border border-alpha-border text-alpha-text-secondary hover:text-alpha-gold transition-colors ml-auto sm:ml-0"
            title="Refresh Feed"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-alpha-gold' : ''}`} />
          </button>
        </div>
      </div>

      {/* Sync Notification Banner */}
      {syncMsg && (
        <div className="p-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 flex items-center justify-between text-emerald-300 text-xs font-mono">
          <span>✓ {syncMsg}</span>
          <button onClick={() => setSyncMsg(null)} className="text-emerald-400 hover:text-white ml-2">✕</button>
        </div>
      )}

      {/* Warnings & Diagnostics Banner */}
      {(status?.is_stale || status?.feed_state === 'DISCONNECTED' || (status?.gap_count ?? 0) > 0) && (
        <div className="p-4 rounded-xl border border-amber-900/70 bg-amber-950/40 flex items-start gap-3 text-amber-200 text-xs font-mono">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-400 mt-0.5" />
          <div>
            <span className="font-bold uppercase tracking-wider block">Market Feed Anomaly Detected:</span>
            {status?.is_stale && (
              <p>• Data feed is stale (&gt;120s since last exchange candle event). Check WebSocket connection.</p>
            )}
            {status?.feed_state === 'DISCONNECTED' && (
              <p>• WebSocket collector is currently DISCONNECTED. Attempting exponential backoff reconnect.</p>
            )}
            {(status?.gap_count ?? 0) > 0 && (
              <p>• {status?.gap_count} sequence gaps identified. REST backfill engine is queued.</p>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl border border-rose-900/60 bg-rose-950/30 flex items-start gap-3 text-rose-300 text-xs font-mono">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-400 mt-0.5" />
          <div>
            <span className="font-semibold">Query Error:</span> {error}
          </div>
        </div>
      )}

      {/* Chart Canvas Card */}
      <div className="p-3.5 sm:p-5 rounded-xl border border-alpha-border bg-alpha-card shadow-sm space-y-4">
        {/* Chart Controls Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 border-b border-alpha-borderSubtle pb-3">
          <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs font-mono">
            <span className="text-white font-semibold">
              BTC/USDT <span className="text-alpha-gold font-normal">({interval})</span>
            </span>

            {hoveredCandle ? (
              <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-[10px] sm:text-[11px] text-alpha-text-secondary bg-alpha-surface px-2.5 py-1 rounded border border-alpha-borderSubtle">
                <span>O: <strong className="text-white">{hoveredCandle.open.toFixed(2)}</strong></span>
                <span>H: <strong className="text-emerald-400">{hoveredCandle.high.toFixed(2)}</strong></span>
                <span>L: <strong className="text-rose-400">{hoveredCandle.low.toFixed(2)}</strong></span>
                <span>C: <strong className="text-white">{hoveredCandle.close.toFixed(2)}</strong></span>
                <span>Vol: <strong className="text-alpha-gold">{hoveredCandle.volume.toFixed(2)}</strong></span>
              </div>
            ) : candles.length > 0 && candles[candles.length - 1] ? (
              <div className="flex items-center gap-3 text-[11px] text-alpha-text-muted">
                <span>Latest Close: <strong className="text-white">${candles[candles.length - 1]!.close.toFixed(2)}</strong></span>
              </div>
            ) : null}
          </div>

          {/* Technical Overlays Toggles */}
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            <button
              onClick={() => setShowSMA20(!showSMA20)}
              className={`px-2.5 py-1 rounded text-[11px] font-mono border transition-colors flex items-center gap-1.5 ${
                showSMA20
                  ? 'bg-amber-400/10 text-amber-300 border-amber-400/40'
                  : 'bg-alpha-surface text-alpha-text-muted border-alpha-borderSubtle'
              }`}
            >
              <span className="w-2 h-0.5 bg-amber-400 rounded-full inline-block" />
              <span>SMA 20</span>
            </button>

            <button
              onClick={() => setShowSMA100(!showSMA100)}
              className={`px-2.5 py-1 rounded text-[11px] font-mono border transition-colors flex items-center gap-1.5 ${
                showSMA100
                  ? 'bg-alpha-gold/15 text-alpha-gold border-alpha-gold/40'
                  : 'bg-alpha-surface text-alpha-text-muted border-alpha-borderSubtle'
              }`}
            >
              <span className="w-2 h-0.5 bg-alpha-gold rounded-full inline-block" />
              <span>SMA 100</span>
            </button>

            <button
              onClick={() => setShowSignals(!showSignals)}
              className={`px-2.5 py-1 rounded text-[11px] font-mono border transition-colors flex items-center gap-1.5 ${
                showSignals
                  ? 'bg-emerald-400/10 text-emerald-300 border-emerald-400/40'
                  : 'bg-alpha-surface text-alpha-text-muted border-alpha-borderSubtle'
              }`}
            >
              <span>▲▼ Signals</span>
            </button>
          </div>
        </div>

        {/* Candlestick SVG Container */}
        {candles.length === 0 ? (
          <div className="py-12 text-center">
            <EmptyState
              icon={<Database className="w-8 h-8" />}
              title="No Historical Candles In Database"
              description="No BTC/USDT candles found for the selected interval. Trigger the Binance market data collector or ingestion CLI."
              phaseRequired={2}
            />
          </div>
        ) : (
          <div className="w-full overflow-x-auto relative">
            <svg
              className="w-full min-w-[700px] select-none"
              style={{ height: `${totalSvgHeight}px` }}
              viewBox={`0 0 ${Math.max(700, candles.length * 14 + paddingLeft + paddingRight)} ${totalSvgHeight}`}
              preserveAspectRatio="none"
              onMouseLeave={() => setHoveredIndex(null)}
            >
              {/* Horizontal grid lines */}
              {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
                const price = minPrice + pct * (maxPrice - minPrice);
                const y = getY(price);
                return (
                  <g key={pct}>
                    <line
                      x1={paddingLeft}
                      y1={y}
                      x2="100%"
                      y2={y}
                      stroke="rgba(255,255,255,0.06)"
                      strokeDasharray="3 3"
                    />
                    <text
                      x={paddingLeft - 8}
                      y={y + 3}
                      fill="#8E8E93"
                      fontSize="9"
                      fontFamily="monospace"
                      textAnchor="end"
                    >
                      ${price.toFixed(0)}
                    </text>
                  </g>
                );
              })}

              {/* Volume separator line */}
              <line
                x1={paddingLeft}
                y1={chartHeight + 10}
                x2="100%"
                y2={chartHeight + 10}
                stroke="rgba(255,255,255,0.12)"
              />
              <text
                x={paddingLeft - 8}
                y={chartHeight + 22}
                fill="#8E8E93"
                fontSize="9"
                fontFamily="monospace"
                textAnchor="end"
              >
                Vol (BTC)
              </text>

              {/* Candlesticks and Volume Bars */}
              {candles.map((candle, idx) => {
                const candleWidth = 8;
                const barSpacing = 14;
                const x = paddingLeft + idx * barSpacing;
                const isGreen = candle.close >= candle.open;
                const bodyTop = getY(Math.max(candle.open, candle.close));
                const bodyBottom = getY(Math.min(candle.open, candle.close));
                const bodyHeight = Math.max(1, bodyBottom - bodyTop);

                const wickTop = getY(candle.high);
                const wickBottom = getY(candle.low);

                const volY = getVolY(candle.volume);
                const volHeight = Math.max(1, chartHeight + volumeHeight - volY);

                const candleColor = isGreen ? '#10B981' : '#F43F5E';
                const isHovered = hoveredIndex === idx;

                return (
                  <g
                    key={candle.open_time}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onClick={() => setHoveredIndex(idx)}
                    className="cursor-pointer"
                  >
                    {/* Hover highlight background column */}
                    {isHovered && (
                      <rect
                        x={x - barSpacing / 2}
                        y={paddingTop}
                        width={barSpacing}
                        height={chartHeight + volumeHeight - paddingTop}
                        fill="rgba(212, 175, 55, 0.08)"
                      />
                    )}

                    {/* High-Low Wick */}
                    <line
                      x1={x}
                      y1={wickTop}
                      x2={x}
                      y2={wickBottom}
                      stroke={candleColor}
                      strokeWidth="1.2"
                    />

                    {/* Candle Body */}
                    <rect
                      x={x - candleWidth / 2}
                      y={bodyTop}
                      width={candleWidth}
                      height={bodyHeight}
                      fill={candleColor}
                      rx="1"
                    />

                    {/* Volume Bar */}
                    <rect
                      x={x - candleWidth / 2}
                      y={volY}
                      width={candleWidth}
                      height={volHeight}
                      fill={candleColor}
                      opacity={isHovered ? 0.8 : 0.35}
                    />

                    {/* Signal Markers */}
                    {showSignals && signalMap.has(candle.open_time) && (() => {
                      const sig = signalMap.get(candle.open_time);
                      if (!sig) return null;
                      if (sig.side === 'buy') {
                        return (
                          <polygon
                            points={`${x},${wickBottom + 6} ${x - 5},${wickBottom + 14} ${x + 5},${wickBottom + 14}`}
                            fill="#10B981"
                            stroke="#042F2E"
                            strokeWidth="1"
                          />
                        );
                      }
                      if (sig.side === 'sell') {
                        return (
                          <polygon
                            points={`${x},${wickTop - 6} ${x - 5},${wickTop - 14} ${x + 5},${wickTop - 14}`}
                            fill="#F43F5E"
                            stroke="#4C0519"
                            strokeWidth="1"
                          />
                        );
                      }
                      return null;
                    })()}
                  </g>
                );
              })}

              {/* SMA 20 Overlay Line */}
              {showSMA20 && (() => {
                const points = sma20
                  .map((val, idx) => {
                    if (val === null) return null;
                    const x = paddingLeft + idx * 14;
                    const y = getY(val);
                    return `${x},${y}`;
                  })
                  .filter((p): p is string => p !== null)
                  .join(' ');

                return (
                  <polyline
                    fill="none"
                    stroke="#FBBF24"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points={points}
                  />
                );
              })()}

              {/* SMA 100 Overlay Line */}
              {showSMA100 && (() => {
                const points = sma100
                  .map((val, idx) => {
                    if (val === null) return null;
                    const x = paddingLeft + idx * 14;
                    const y = getY(val);
                    return `${x},${y}`;
                  })
                  .filter((p): p is string => p !== null)
                  .join(' ');

                return (
                  <polyline
                    fill="none"
                    stroke="#D4AF37"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points={points}
                  />
                );
              })()}
            </svg>
          </div>
        )}
      </div>

      {/* Observation Table */}
      <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-alpha-gold" />
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
              BTC/USDT OHLCV Observations ({candles.length} Bars)
            </h2>
          </div>
          <span className="text-[11px] font-mono text-alpha-text-muted">
            Interval: {interval} • Order: Chronological (ASC)
          </span>
        </div>

        <div className="overflow-x-auto max-h-80 overflow-y-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-alpha-borderSubtle text-alpha-text-muted sticky top-0 bg-alpha-card">
                <th className="py-2.5 pr-4">Open Time (UTC)</th>
                <th className="py-2.5 pr-4">Open</th>
                <th className="py-2.5 pr-4">High</th>
                <th className="py-2.5 pr-4">Low</th>
                <th className="py-2.5 pr-4">Close</th>
                <th className="py-2.5 pr-4">Volume (BTC)</th>
                <th className="py-2.5 pr-4">Trades</th>
                <th className="py-2.5">State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-alpha-borderSubtle/60 text-alpha-text-secondary">
              {candles.slice(-30).reverse().map((c) => (
                <tr key={c.open_time} className="hover:bg-alpha-cardHover transition-colors">
                  <td className="py-2 pr-4 text-alpha-text-muted">
                    {new Date(c.open_time).toISOString().replace('T', ' ').slice(0, 19)}
                  </td>
                  <td className="py-2 pr-4">${c.open.toFixed(2)}</td>
                  <td className="py-2 pr-4 text-emerald-400">${c.high.toFixed(2)}</td>
                  <td className="py-2 pr-4 text-rose-400">${c.low.toFixed(2)}</td>
                  <td className="py-2 pr-4 font-semibold text-white">${c.close.toFixed(2)}</td>
                  <td className="py-2 pr-4 text-alpha-gold">{c.volume.toFixed(4)}</td>
                  <td className="py-2 pr-4">{c.trades_count}</td>
                  <td className="py-2">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${
                        c.is_closed
                          ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40'
                          : 'bg-amber-950/40 text-amber-400 border-amber-800/40 animate-pulse'
                      }`}
                    >
                      {c.is_closed ? 'FINAL' : 'OPEN'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
