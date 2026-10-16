import React, { useState, useEffect } from 'react';
import {
  History,
  Play,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
  Layers,
  Clock,
  RefreshCw,
  Sliders,
  DollarSign,
  AlertTriangle,
} from 'lucide-react';
import {
  BacktestRun,
  BacktestCreateRequest,
  PerformanceAnalyticsResponse,
  StrategyInfo,
} from '../types';
import {
  createBacktest,
  fetchBacktestRuns,
  fetchBacktestRun,
  fetchPerformanceAnalytics,
  fetchStrategies,
} from '../services/api';
import { EmptyState } from '../components/common/EmptyState';

export const BacktestPage: React.FC = () => {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null);
  const [analytics, setAnalytics] = useState<PerformanceAnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [selectedStrategy, setSelectedStrategy] = useState<string>('trend_following');
  const [symbol] = useState<string>('BTCUSDT');
  const [interval] = useState<string>('1m');
  const [initialCash, setInitialCash] = useState<number>(10000);
  const [makerFeeBps, setMakerFeeBps] = useState<number>(8.0);
  const [takerFeeBps, setTakerFeeBps] = useState<number>(10.0);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);
  const [includeStress, setIncludeStress] = useState<boolean>(true);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [strats, runList, perf] = await Promise.all([
        fetchStrategies().catch(() => []),
        fetchBacktestRuns().catch(() => ({ count: 0, backtests: [] })),
        fetchPerformanceAnalytics().catch(() => null),
      ]);
      setStrategies(strats);
      setRuns(runList.backtests);
      setAnalytics(perf);

      const firstRun = runList.backtests[0];
      if (firstRun && !selectedRun) {
        // Load details of the latest run
        const latest = await fetchBacktestRun(firstRun.id).catch(() => null);
        if (latest) setSelectedRun(latest);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load backtest data.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunBacktest = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSimulating(true);
    setError(null);

    const payload: BacktestCreateRequest = {
      strategy_id: selectedStrategy,
      symbol,
      interval,
      initial_cash: initialCash,
      cost_assumptions: {
        maker_fee_bps: makerFeeBps,
        taker_fee_bps: takerFeeBps,
        slippage_bps: slippageBps,
      },
      stress_scenarios: includeStress,
    };

    try {
      const runResult = await createBacktest(payload);
      setSelectedRun(runResult);
      // Reload runs list & analytics
      const [runList, perf] = await Promise.all([
        fetchBacktestRuns(),
        fetchPerformanceAnalytics(),
      ]);
      setRuns(runList.backtests);
      setAnalytics(perf);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Simulation failed.');
    } finally {
      setIsSimulating(false);
    }
  };

  const handleSelectRun = async (runId: string) => {
    setIsLoading(true);
    try {
      const run = await fetchBacktestRun(runId);
      setSelectedRun(run);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load run details.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-alpha-text-primary flex items-center gap-3">
            <History className="w-6 h-6 text-alpha-gold" />
            <span>Deterministic Historical Backtest Engine</span>
          </h1>
          <p className="text-sm text-alpha-text-secondary mt-1">
            Strict Next-Bar Event-Driven Execution, Explicit Slippage & Fee Drag, Walk-Forward Validation & Regime Stress Testing
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={isLoading || isSimulating}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg border border-alpha-border bg-alpha-surface text-alpha-text-secondary hover:text-alpha-gold hover:border-alpha-gold transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh Engine
        </button>
      </div>

      {/* Global Performance Summary Cards */}
      {analytics && analytics.total_backtests > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-alpha-card border border-alpha-border rounded-xl p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary">Simulations</span>
              <Layers className="w-4 h-4 text-alpha-gold" />
            </div>
            <p className="text-2xl font-mono font-bold text-alpha-text-primary mt-2">
              {analytics.total_backtests}
            </p>
            <p className="text-[11px] text-alpha-text-secondary mt-1">Audited Historical Runs</p>
          </div>

          <div className="bg-alpha-card border border-alpha-border rounded-xl p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary">Avg Net Return</span>
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            </div>
            <p className={`text-2xl font-mono font-bold mt-2 ${analytics.avg_net_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {analytics.avg_net_return_pct >= 0 ? '+' : ''}{analytics.avg_net_return_pct.toFixed(2)}%
            </p>
            <p className="text-[11px] text-alpha-text-secondary mt-1">Post Fees & Slippage</p>
          </div>

          <div className="bg-alpha-card border border-alpha-border rounded-xl p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary">Avg Sharpe Ratio</span>
              <Sliders className="w-4 h-4 text-alpha-gold" />
            </div>
            <p className="text-2xl font-mono font-bold text-alpha-text-primary mt-2">
              {analytics.avg_sharpe_ratio.toFixed(2)}
            </p>
            <p className="text-[11px] text-alpha-text-secondary mt-1">525,600 min/yr (24/7/365)</p>
          </div>

          <div className="bg-alpha-card border border-alpha-border rounded-xl p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary">Avg Max Drawdown</span>
              <TrendingDown className="w-4 h-4 text-rose-400" />
            </div>
            <p className="text-2xl font-mono font-bold text-rose-400 mt-2">
              {analytics.avg_max_drawdown_pct.toFixed(2)}%
            </p>
            <p className="text-[11px] text-alpha-text-secondary mt-1">Peak-to-Trough Loss</p>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-rose-300">Simulation Error</h4>
            <p className="text-xs text-rose-400/90 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Main Grid: Launcher on Left, Results on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Form & Recent Runs */}
        <div className="lg:col-span-4 space-y-6">
          {/* Backtest Configuration Card */}
          <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm">
            <h2 className="text-base font-semibold text-alpha-text-primary flex items-center gap-2 mb-4">
              <Play className="w-4 h-4 text-alpha-gold" />
              <span>Launch Historical Simulation</span>
            </h2>

            <form onSubmit={handleRunBacktest} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-alpha-text-secondary mb-1">
                  Quantitative Strategy
                </label>
                <select
                  value={selectedStrategy}
                  onChange={(e) => setSelectedStrategy(e.target.value)}
                  className="w-full bg-alpha-surface border border-alpha-border rounded-lg px-3 py-2 text-xs text-alpha-text-primary focus:outline-none focus:border-alpha-gold"
                >
                  {strategies.length > 0 ? (
                    strategies.map((s) => (
                      <option key={s.strategy_id} value={s.strategy_id}>
                        {s.name} ({s.strategy_id})
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="trend_following">Trend Following (EMA 20/100, Volatility Filter)</option>
                      <option value="mean_reversion">Mean Reversion (60-Lookback, Z-Score 2.0)</option>
                      <option value="momentum">Momentum (Multi-period, Cost Hurdle)</option>
                    </>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-alpha-text-secondary mb-1">
                  Initial Cash Capital ($ USD)
                </label>
                <div className="relative">
                  <DollarSign className="w-3.5 h-3.5 text-alpha-text-secondary absolute left-3 top-2.5" />
                  <input
                    type="number"
                    min="100"
                    step="100"
                    value={initialCash}
                    onChange={(e) => setInitialCash(Number(e.target.value))}
                    className="w-full bg-alpha-surface border border-alpha-border rounded-lg pl-8 pr-3 py-2 text-xs text-alpha-text-primary focus:outline-none focus:border-alpha-gold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-alpha-text-secondary mb-1">
                    Taker Fee (bps)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    value={takerFeeBps}
                    onChange={(e) => setTakerFeeBps(Number(e.target.value))}
                    className="w-full bg-alpha-surface border border-alpha-border rounded-lg px-3 py-2 text-xs text-alpha-text-primary focus:outline-none focus:border-alpha-gold"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-alpha-text-secondary mb-1">
                    Maker Fee (bps)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    value={makerFeeBps}
                    onChange={(e) => setMakerFeeBps(Number(e.target.value))}
                    className="w-full bg-alpha-surface border border-alpha-border rounded-lg px-3 py-2 text-xs text-alpha-text-primary focus:outline-none focus:border-alpha-gold"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-alpha-text-secondary mb-1">
                  Adverse Slippage (bps)
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={slippageBps}
                  onChange={(e) => setSlippageBps(Number(e.target.value))}
                  className="w-full bg-alpha-surface border border-alpha-border rounded-lg px-3 py-2 text-xs text-alpha-text-primary focus:outline-none focus:border-alpha-gold"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="includeStress"
                  checked={includeStress}
                  onChange={(e) => setIncludeStress(e.target.checked)}
                  className="rounded border-alpha-border text-alpha-gold focus:ring-alpha-gold bg-alpha-surface"
                />
                <label htmlFor="includeStress" className="text-xs text-alpha-text-secondary cursor-pointer">
                  Run Multi-Scenario Stress Tests (2x/5x Fees, 3x Slippage, 1-Bar Lag)
                </label>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isSimulating}
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-alpha-gold text-black hover:bg-alpha-gold/90 transition-colors disabled:opacity-50"
                >
                  {isSimulating ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Simulating Chronological Bars...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      <span>Execute Deterministic Backtest</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Historical Runs List */}
          <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary mb-3 flex items-center justify-between">
              <span>Audited Simulations ({runs.length})</span>
            </h3>
            {runs.length === 0 ? (
              <p className="text-xs text-alpha-text-secondary py-4 text-center">
                No backtest simulations recorded yet.
              </p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {runs.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => handleSelectRun(r.id)}
                    className={`w-full text-left p-3 rounded-lg border text-xs transition-colors flex items-center justify-between ${
                      selectedRun?.id === r.id
                        ? 'border-alpha-gold bg-alpha-gold/10'
                        : 'border-alpha-border bg-alpha-surface hover:border-alpha-gold/50'
                    }`}
                  >
                    <div>
                      <div className="font-semibold text-alpha-text-primary capitalize">
                        {r.strategy_id.replace('_', ' ')}
                      </div>
                      <div className="text-[11px] text-alpha-text-secondary mt-0.5 flex items-center gap-2">
                        <span>{r.candle_count} candles</span>
                        <span>•</span>
                        <span>{r.total_trades} trades</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`font-mono font-bold ${r.net_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {r.net_return_pct >= 0 ? '+' : ''}{r.net_return_pct.toFixed(2)}%
                      </div>
                      <div className="text-[10px] text-alpha-text-secondary font-mono">
                        SR {r.sharpe_ratio.toFixed(1)}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Active Simulation Results */}
        <div className="lg:col-span-8 space-y-6">
          {!selectedRun ? (
            <div className="bg-alpha-card border border-alpha-border rounded-xl p-8 text-center">
              <EmptyState
                icon={<History className="w-8 h-8" />}
                title="No Backtest Selected"
                description="Launch a deterministic historical simulation on the left or select an audited run from the list to inspect trade fills, equity curves, slippage drag, and regime stress tests."
                phaseRequired={4}
              />
            </div>
          ) : (
            <div className="space-y-6">
              {/* Detailed Metrics Panel */}
              <div className="bg-alpha-card border border-alpha-border rounded-xl p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-alpha-border">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-alpha-gold/20 text-alpha-gold rounded border border-alpha-gold/40">
                        {selectedRun.status}
                      </span>
                      <h2 className="text-lg font-bold text-alpha-text-primary capitalize">
                        {selectedRun.strategy_id.replace('_', ' ')} Simulation
                      </h2>
                    </div>
                    <p className="text-xs text-alpha-text-secondary mt-1 font-mono">
                      Dataset Fingerprint: {selectedRun.dataset_fingerprint.substring(0, 16)}... | Symbol: {selectedRun.symbol} ({selectedRun.interval})
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-alpha-text-secondary">Net Realized Equity</span>
                    <p className="text-2xl font-mono font-bold text-alpha-text-primary">
                      ${((selectedRun.metrics.final_equity as number) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                  </div>
                </div>

                {/* Core Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
                  <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
                    <span className="text-[11px] uppercase tracking-wider text-alpha-text-secondary font-semibold">Net Return</span>
                    <p className={`text-xl font-mono font-bold mt-1 ${selectedRun.net_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {selectedRun.net_return_pct >= 0 ? '+' : ''}{selectedRun.net_return_pct.toFixed(2)}%
                    </p>
                    <span className="text-[10px] text-alpha-text-secondary">Gross: {((selectedRun.metrics.gross_return_pct as number) || 0).toFixed(2)}%</span>
                  </div>

                  <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
                    <span className="text-[11px] uppercase tracking-wider text-alpha-text-secondary font-semibold">Buy & Hold</span>
                    <p className={`text-xl font-mono font-bold mt-1 ${((selectedRun.metrics.buy_and_hold_return_pct as number) || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {((selectedRun.metrics.buy_and_hold_return_pct as number) || 0) >= 0 ? '+' : ''}
                      {((selectedRun.metrics.buy_and_hold_return_pct as number) || 0).toFixed(2)}%
                    </p>
                    <span className="text-[10px] text-alpha-text-secondary">Passive Benchmark</span>
                  </div>

                  <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
                    <span className="text-[11px] uppercase tracking-wider text-alpha-text-secondary font-semibold">Sharpe / Sortino</span>
                    <p className="text-xl font-mono font-bold text-alpha-text-primary mt-1">
                      {selectedRun.sharpe_ratio.toFixed(2)}
                    </p>
                    <span className="text-[10px] text-alpha-text-secondary">
                      Sortino: {((selectedRun.metrics.sortino_ratio as number) || 0).toFixed(2)}
                    </span>
                  </div>

                  <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
                    <span className="text-[11px] uppercase tracking-wider text-alpha-text-secondary font-semibold">Max Drawdown</span>
                    <p className="text-xl font-mono font-bold text-rose-400 mt-1">
                      {selectedRun.max_drawdown_pct.toFixed(2)}%
                    </p>
                    <span className="text-[10px] text-alpha-text-secondary">Peak-to-Trough</span>
                  </div>
                </div>

                {/* Secondary Metrics Bar */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4">
                  <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
                    <span className="text-[11px] uppercase tracking-wider text-alpha-text-secondary font-semibold">Trades / Win Rate</span>
                    <p className="text-sm font-mono font-bold text-alpha-text-primary mt-1">
                      {selectedRun.total_trades} trades ({selectedRun.win_rate_pct.toFixed(1)}% win)
                    </p>
                    <span className="text-[10px] text-alpha-text-secondary">PF: {selectedRun.profit_factor ? selectedRun.profit_factor.toFixed(2) : 'N/A'}</span>
                  </div>

                  <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
                    <span className="text-[11px] uppercase tracking-wider text-alpha-text-secondary font-semibold">Turnover / Exposure</span>
                    <p className="text-sm font-mono font-bold text-alpha-text-primary mt-1">
                      {((selectedRun.metrics.turnover as number) || 0).toFixed(2)}x capital
                    </p>
                    <span className="text-[10px] text-alpha-text-secondary">Market Exp: {((selectedRun.metrics.market_exposure_pct as number) || 0).toFixed(1)}%</span>
                  </div>

                  <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
                    <span className="text-[11px] uppercase tracking-wider text-alpha-text-secondary font-semibold">Fees Paid</span>
                    <p className="text-sm font-mono font-bold text-alpha-gold mt-1">
                      ${((selectedRun.metrics.total_fees_paid as number) || 0).toFixed(2)}
                    </p>
                    <span className="text-[10px] text-alpha-text-secondary">Drag: {((selectedRun.metrics.fee_drag_pct as number) || 0).toFixed(2)}%</span>
                  </div>

                  <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
                    <span className="text-[11px] uppercase tracking-wider text-alpha-text-secondary font-semibold">Slippage Drag</span>
                    <p className="text-sm font-mono font-bold text-rose-300 mt-1">
                      ${((selectedRun.metrics.total_slippage_cost as number) || 0).toFixed(2)}
                    </p>
                    <span className="text-[10px] text-alpha-text-secondary">Drag: {((selectedRun.metrics.slippage_drag_pct as number) || 0).toFixed(2)}%</span>
                  </div>
                </div>
              </div>

              {/* Stress Test Scenarios */}
              {selectedRun.stress_test_results && Object.keys(selectedRun.stress_test_results).length > 0 && (
                <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary mb-3 flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-alpha-gold" />
                    <span>Cost Sensitivity & Execution Stress Tests</span>
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-alpha-border text-alpha-text-secondary font-mono">
                          <th className="text-left pb-2">Stress Scenario</th>
                          <th className="text-right pb-2">Net Return</th>
                          <th className="text-right pb-2">Max Drawdown</th>
                          <th className="text-right pb-2">Modeled Fees</th>
                          <th className="text-right pb-2">Modeled Slippage</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-alpha-border/40 font-mono">
                        {Object.entries(selectedRun.stress_test_results).map(([scenario, res]) => (
                          <tr key={scenario} className="hover:bg-alpha-surface/50">
                            <td className="py-2.5 font-semibold text-alpha-text-primary capitalize">
                              {scenario.replace(/_/g, ' ')}
                            </td>
                            <td className={`py-2.5 text-right font-bold ${res.net_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {res.net_return_pct >= 0 ? '+' : ''}{res.net_return_pct.toFixed(2)}%
                            </td>
                            <td className="py-2.5 text-right text-rose-400">
                              {res.max_drawdown_pct.toFixed(2)}%
                            </td>
                            <td className="py-2.5 text-right text-alpha-text-secondary">
                              ${res.total_fees.toFixed(2)}
                            </td>
                            <td className="py-2.5 text-right text-alpha-text-secondary">
                              ${res.total_slippage.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Market Regime Breakdown */}
              {selectedRun.regime_performance && Object.keys(selectedRun.regime_performance).length > 0 && (
                <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary mb-3 flex items-center gap-2">
                    <Layers className="w-4 h-4 text-alpha-gold" />
                    <span>Market Regime Decomposition</span>
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {Object.entries(selectedRun.regime_performance).map(([regime, perf]) => (
                      <div key={regime} className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
                        <span className="text-[11px] font-semibold text-alpha-text-secondary capitalize">{regime}</span>
                        <p className={`text-sm font-mono font-bold mt-1 ${perf.gross_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {perf.gross_return_pct >= 0 ? '+' : ''}{perf.gross_return_pct.toFixed(2)}%
                        </p>
                        <p className="text-[10px] text-alpha-text-secondary mt-0.5 font-mono">
                          {perf.time_pct.toFixed(1)}% time ({perf.candles_count} bars)
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Executed Trades Table */}
              <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary mb-3 flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-alpha-gold" />
                    <span>Simulated Next-Bar Order Executions ({selectedRun.trades?.length || 0})</span>
                  </span>
                </h3>
                {!selectedRun.trades || selectedRun.trades.length === 0 ? (
                  <p className="text-xs text-alpha-text-secondary py-4 text-center">
                    No order fills triggered under strategy signal thresholds.
                  </p>
                ) : (
                  <div className="overflow-x-auto max-h-80 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-alpha-border text-alpha-text-secondary font-mono">
                          <th className="text-left pb-2">Time (UTC)</th>
                          <th className="text-left pb-2">Side</th>
                          <th className="text-right pb-2">Fill Price</th>
                          <th className="text-right pb-2">Qty</th>
                          <th className="text-right pb-2">Notional</th>
                          <th className="text-right pb-2">Fee</th>
                          <th className="text-right pb-2">Slippage</th>
                          <th className="text-right pb-2">Net Realized</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-alpha-border/40 font-mono">
                        {selectedRun.trades.map((t) => (
                          <tr key={t.trade_id} className="hover:bg-alpha-surface/50">
                            <td className="py-2 text-alpha-text-secondary">
                              {new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            </td>
                            <td className="py-2">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                                t.side === 'buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                              }`}>
                                {t.side}
                              </span>
                            </td>
                            <td className="py-2 text-right text-alpha-text-primary">
                              ${t.fill_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                            <td className="py-2 text-right text-alpha-text-secondary">{t.quantity.toFixed(4)}</td>
                            <td className="py-2 text-right text-alpha-text-secondary">${t.gross_notional.toFixed(2)}</td>
                            <td className="py-2 text-right text-alpha-gold">${t.fee.toFixed(2)}</td>
                            <td className="py-2 text-right text-rose-300">${t.slippage_cost.toFixed(2)}</td>
                            <td className={`py-2 text-right font-bold ${
                              t.realized_net_pnl > 0 ? 'text-emerald-400' : t.realized_net_pnl < 0 ? 'text-rose-400' : 'text-alpha-text-secondary'
                            }`}>
                              ${t.realized_net_pnl.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
export default BacktestPage;
