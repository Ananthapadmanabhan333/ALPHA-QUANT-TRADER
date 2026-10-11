import React, { useEffect, useState, useCallback } from 'react';
import {
  TrendingUp,
  RefreshCw,
  Clock,
  Database,
  Radio,
  AlertCircle,
  Hash,
  DownloadCloud,
} from 'lucide-react';
import { fetchCandles, fetchMarketStatus } from '../services/api';
import { MarketCandle, MarketStatusResponse } from '../types';
import { EmptyState } from '../components/common/EmptyState';
import { HealthBadge } from '../components/common/HealthBadge';

export const MarketDataPage: React.FC = () => {
  const [interval, setInterval] = useState<'1m' | '5m' | '15m'>('1m');
  const [symbol] = useState<string>('BTCUSDT');
  const [candles, setCandles] = useState<MarketCandle[]>([]);
  const [status, setStatus] = useState<MarketStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [candlesRes, statusRes] = await Promise.all([
        fetchCandles(symbol, interval, 50, false).catch(() => ({ symbol, interval, count: 0, only_closed: false, candles: [] })),
        fetchMarketStatus(symbol, interval).catch(() => null),
      ]);
      setCandles(candlesRes.candles);
      setStatus(statusRes);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to query market data';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [symbol, interval]);

  useEffect(() => {
    loadData();
    const timer = window.setInterval(loadData, 10000);
    return () => clearInterval(timer);
  }, [loadData]);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Top Banner & Interval Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-alpha-text-primary flex items-center gap-3">
            <TrendingUp className="w-6 h-6 text-alpha-gold" />
            <span>Public Market Data Engine</span>
            <span className="text-xs font-mono font-medium text-alpha-gold px-2 py-0.5 rounded bg-alpha-gold/10 border border-alpha-gold/30">
              PHASE 2
            </span>
          </h1>
          <p className="text-sm text-alpha-text-secondary mt-1">
            Binance Spot public market data adapter • BTC/USDT OHLCV storage • TimescaleDB partitioning
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Interval Selector */}
          <div className="flex items-center bg-alpha-card rounded-lg p-1 border border-alpha-border">
            {(['1m', '5m', '15m'] as const).map((int) => (
              <button
                key={int}
                onClick={() => setInterval(int)}
                className={`px-3 py-1 text-xs font-mono rounded font-medium transition-colors ${
                  interval === int
                    ? 'bg-alpha-gold text-black font-semibold'
                    : 'text-alpha-text-secondary hover:text-white'
                }`}
              >
                {int}
              </button>
            ))}
          </div>

          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-lg bg-alpha-card border border-alpha-border text-alpha-text-secondary hover:text-alpha-gold transition-colors"
            title="Refresh Feed"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-alpha-gold' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-rose-900/60 bg-rose-950/30 flex items-start gap-3 text-rose-300 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400 mt-0.5" />
          <div>
            <span className="font-semibold">Feed Error:</span> {error}
          </div>
        </div>
      )}

      {/* Feed Diagnostics Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Feed State */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase text-alpha-text-muted">Feed State</span>
            <Radio className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="text-lg font-bold font-mono text-alpha-text-primary">
            {status?.feed_state || 'STANDBY'}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-alpha-text-secondary">WebSocket:</span>
            <HealthBadge
              status={status?.connected ? 'healthy' : 'degraded'}
              label={status?.connected ? 'Online' : 'Standby'}
            />
          </div>
        </div>

        {/* Saved Candles in DB */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase text-alpha-text-muted">Candles Stored</span>
            <Database className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="text-2xl font-bold font-mono text-alpha-text-primary">
            {candles.length}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs font-mono text-alpha-text-muted">
            <span>Deduplication:</span>
            <span className="text-emerald-400">Enforced</span>
          </div>
        </div>

        {/* Sequence Gaps */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase text-alpha-text-muted">Sequence Gaps</span>
            <Hash className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="text-2xl font-bold font-mono text-alpha-text-primary">
            {status?.gap_count ?? 0}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs font-mono text-alpha-text-muted">
            <span>Auto-Backfill:</span>
            <span className="text-alpha-gold">Enabled</span>
          </div>
        </div>

        {/* Rate Limiter */}
        <div className="p-5 rounded-xl border border-alpha-border bg-alpha-card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase text-alpha-text-muted">Rate Limit Weight</span>
            <Clock className="w-4 h-4 text-alpha-gold" />
          </div>
          <div className="text-2xl font-bold font-mono text-alpha-text-primary">
            {status?.rate_limit_remaining ?? 1200}
            <span className="text-xs text-alpha-text-muted font-normal"> / 1200</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs font-mono text-alpha-text-muted">
            <span>IP Weight Window:</span>
            <span>60s Sliding</span>
          </div>
        </div>
      </div>

      {/* Main Candles Display */}
      {candles.length === 0 ? (
        <div className="py-6">
          <EmptyState
            icon={<DownloadCloud className="w-7 h-7" />}
            title="No BTC/USDT Market Candles Stored"
            description="Run the public market data ingestion CLI or trigger the REST backfill endpoint to download genuine historical BTC/USDT klines into TimescaleDB. Zero synthetic data generated."
            phaseRequired={2}
            actionText="Refresh Status"
            actionHref="/market-data"
          />
        </div>
      ) : (
        <div className="p-6 rounded-xl border border-alpha-border bg-alpha-card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-alpha-text-muted flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-alpha-gold" />
              <span>BTC/USDT OHLCV Observations ({interval})</span>
            </h2>
            <span className="text-xs font-mono text-alpha-text-muted">
              Showing {candles.length} latest candles (UTC)
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-alpha-borderSubtle text-alpha-text-muted">
                  <th className="py-2.5 pr-4">Open Time (UTC)</th>
                  <th className="py-2.5 pr-4">Open</th>
                  <th className="py-2.5 pr-4">High</th>
                  <th className="py-2.5 pr-4">Low</th>
                  <th className="py-2.5 pr-4">Close</th>
                  <th className="py-2.5 pr-4">Volume (BTC)</th>
                  <th className="py-2.5 pr-4">Trades</th>
                  <th className="py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-alpha-borderSubtle text-alpha-text-secondary">
                {candles.map((c) => (
                  <tr key={c.open_time} className="hover:bg-alpha-cardHover transition-colors">
                    <td className="py-2.5 pr-4 text-alpha-text-muted">
                      {new Date(c.open_time).toISOString().replace('T', ' ').slice(0, 19)}
                    </td>
                    <td className="py-2.5 pr-4">{c.open.toFixed(2)}</td>
                    <td className="py-2.5 pr-4 text-emerald-400">{c.high.toFixed(2)}</td>
                    <td className="py-2.5 pr-4 text-rose-400">{c.low.toFixed(2)}</td>
                    <td className="py-2.5 pr-4 font-semibold text-alpha-text-primary">
                      {c.close.toFixed(2)}
                    </td>
                    <td className="py-2.5 pr-4">{c.volume.toFixed(4)}</td>
                    <td className="py-2.5 pr-4">{c.trades_count}</td>
                    <td className="py-2.5">
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
      )}
    </div>
  );
};
