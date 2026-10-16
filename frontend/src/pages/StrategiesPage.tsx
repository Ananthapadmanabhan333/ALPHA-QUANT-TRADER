import React, { useState, useEffect, useCallback } from 'react';
import {
  LineChart,
  Play,
  Square,
  Zap,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  CheckCircle,
} from 'lucide-react';
import {
  fetchStrategies,
  runStrategy,
  fetchExperiments,
  fetchExperimentDetails,
  fetchPaperTradingStatus,
  startPaperTrading,
  stopPaperTrading,
} from '../services/api';
import {
  StrategyInfo,
  StrategyExperiment,
  PaperTradingStatus,
} from '../types';

export const StrategiesPage: React.FC = () => {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>('trend_following');
  const [experiments, setExperiments] = useState<StrategyExperiment[]>([]);
  const [activeExperiment, setActiveExperiment] = useState<StrategyExperiment | null>(null);
  const [paperStatus, setPaperStatus] = useState<PaperTradingStatus | null>(null);

  const [executing, setExecuting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Modal State for Enabling Paper Execution
  const [showStartModal, setShowStartModal] = useState<boolean>(false);
  const [showStopModal, setShowStopModal] = useState<boolean>(false);
  const [isStartingOrStopping, setIsStartingOrStopping] = useState<boolean>(false);

  // Config parameters for starting paper trading
  const [symbol, setSymbol] = useState<string>('BTCUSDT');
  const [interval, setInterval] = useState<string>('1m');
  const [pollIntervalSeconds, setPollIntervalSeconds] = useState<number>(5);
  const [orderSizePct, setOrderSizePct] = useState<number>(5.0);

  const loadInitialData = useCallback(async () => {
    setError(null);
    try {
      const [stratData, expData, statusData] = await Promise.all([
        fetchStrategies().catch(() => []),
        fetchExperiments(undefined, undefined, 20).catch(() => ({ count: 0, experiments: [] })),
        fetchPaperTradingStatus().catch(() => null),
      ]);
      setStrategies(stratData);
      setPaperStatus(statusData);

      const expList = expData.experiments || [];
      setExperiments(expList);
      if (expList.length > 0 && expList[0]) {
        const newest = await fetchExperimentDetails(expList[0].id).catch(() => null);
        if (newest) setActiveExperiment(newest);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load strategy telemetry');
    }
  }, []);

  useEffect(() => {
    loadInitialData();
    const intervalTimer = window.setInterval(async () => {
      const statusData = await fetchPaperTradingStatus().catch(() => null);
      setPaperStatus(statusData);
    }, 4000);
    return () => clearInterval(intervalTimer);
  }, [loadInitialData]);

  const handleRunEvaluation = async (strategyId: string) => {
    setExecuting(true);
    setError(null);
    setActionSuccess(null);
    try {
      const exp = await runStrategy({
        strategy_id: strategyId,
        symbol: 'BTCUSDT',
        interval: '1m',
        limit: 300,
      });
      setActiveExperiment(exp);
      const expList = await fetchExperiments();
      setExperiments(expList.experiments || []);
      setActionSuccess(`Evaluation complete: ${exp.total_signals} signals generated on ${exp.candle_count} candles.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Strategy feature evaluation failed');
    } finally {
      setExecuting(false);
    }
  };

  const handleConfirmStartPaper = async () => {
    setIsStartingOrStopping(true);
    setError(null);
    setActionSuccess(null);
    try {
      const selectedStrat = strategies.find((s) => s.strategy_id === selectedStrategyId);
      const res = await startPaperTrading({
        strategy_id: selectedStrategyId,
        symbol,
        interval,
        poll_interval_seconds: pollIntervalSeconds,
        order_size_pct: orderSizePct,
        parameters: selectedStrat?.candidate_parameters ?? {},
      });
      setShowStartModal(false);
      setActionSuccess(`Paper execution successfully activated: ${res.message}`);
      const updatedStatus = await fetchPaperTradingStatus();
      setPaperStatus(updatedStatus);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start paper execution');
    } finally {
      setIsStartingOrStopping(false);
    }
  };

  const handleConfirmStopPaper = async () => {
    setIsStartingOrStopping(true);
    setError(null);
    setActionSuccess(null);
    try {
      const res = await stopPaperTrading();
      setShowStopModal(false);
      setActionSuccess(`Paper execution stopped: ${res.message} (${res.cycles_completed} cycles completed).`);
      const updatedStatus = await fetchPaperTradingStatus();
      setPaperStatus(updatedStatus);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to halt paper execution');
    } finally {
      setIsStartingOrStopping(false);
    }
  };

  const handleSelectExperiment = async (expId: string) => {
    try {
      const details = await fetchExperimentDetails(expId);
      setActiveExperiment(details);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load experiment');
    }
  };

  const selectedStrategy = strategies.find((s) => s.strategy_id === selectedStrategyId);

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
              <LineChart className="w-6 h-6 text-alpha-gold" />
              <span>QUANTITATIVE STRATEGIES</span>
            </h1>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-alpha-gold/10 text-alpha-gold border border-alpha-gold/30">
              FEATURE PIPELINE & RUNNER
            </span>
          </div>
          <p className="text-xs text-alpha-text-secondary mt-1 font-mono">
            Pure Functional Signals • Lookahead Bias Prevention • Central Risk Gate Interlock
          </p>
        </div>

        {/* Global Paper Runner Controls */}
        <div className="flex items-center gap-3">
          {paperStatus?.is_running ? (
            <button
              onClick={() => setShowStopModal(true)}
              className="px-3.5 py-2 bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs font-mono rounded-lg transition-colors flex items-center gap-2 shadow-sm"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Halt Paper Execution</span>
            </button>
          ) : (
            <button
              onClick={() => setShowStartModal(true)}
              className="px-3.5 py-2 bg-alpha-gold hover:bg-alpha-gold/90 text-black font-semibold text-xs font-mono rounded-lg transition-colors flex items-center gap-2 shadow-sm"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Enable Paper Execution</span>
            </button>
          )}

          <button
            onClick={() => handleRunEvaluation(selectedStrategyId)}
            disabled={executing}
            className="px-3.5 py-2 bg-alpha-card border border-alpha-border hover:border-alpha-gold text-white font-medium text-xs font-mono rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            {executing ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-alpha-gold" />
            ) : (
              <Zap className="w-3.5 h-3.5 text-alpha-gold" />
            )}
            <span>Evaluate Features</span>
          </button>
        </div>
      </div>

      {/* Runner Status Banner */}
      <div className="p-4 rounded-xl border border-alpha-border bg-alpha-card flex flex-col sm:flex-row sm:items-center justify-between gap-3 font-mono text-xs">
        <div className="flex items-center gap-3">
          <span
            className={`w-3 h-3 rounded-full ${
              paperStatus?.is_running ? 'bg-emerald-400 animate-ping' : 'bg-neutral-600'
            }`}
          />
          <div>
            <span className="text-white font-semibold">Orchestrator Lifecycle: </span>
            <span className={paperStatus?.is_running ? 'text-emerald-400' : 'text-neutral-400'}>
              {paperStatus?.is_running ? 'ACTIVE RUNNING' : 'STOPPED (IDLE)'}
            </span>
            {paperStatus?.strategy_id && (
              <span className="text-alpha-text-muted ml-2">
                [Active: <strong className="text-alpha-gold">{paperStatus.strategy_id}</strong> on {paperStatus.symbol}]
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4 text-alpha-text-muted text-[11px]">
          <span>Cycles: <strong className="text-white">{paperStatus?.cycles_completed ?? 0}</strong></span>
          <span>•</span>
          <span>Signals: <strong className="text-white">{paperStatus?.signals_evaluated ?? 0}</strong></span>
          <span>•</span>
          <span>Orders: <strong className="text-white">{paperStatus?.orders_submitted ?? 0}</strong></span>
        </div>
      </div>

      {/* Notices & Banners */}
      {actionSuccess && (
        <div className="p-4 rounded-xl border border-emerald-900/60 bg-emerald-950/30 flex items-start gap-3 text-emerald-300 text-xs font-mono">
          <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl border border-rose-900/60 bg-rose-950/30 flex items-start gap-3 text-rose-300 text-xs font-mono">
          <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Baseline Strategy Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {strategies.map((strat) => {
          const isSelected = selectedStrategyId === strat.strategy_id;
          const isRunning = paperStatus?.is_running && paperStatus?.strategy_id === strat.strategy_id;

          return (
            <div
              key={strat.strategy_id}
              onClick={() => setSelectedStrategyId(strat.strategy_id)}
              className={`p-5 rounded-xl border transition cursor-pointer flex flex-col justify-between ${
                isSelected
                  ? 'bg-alpha-card border-alpha-gold shadow-md'
                  : 'bg-alpha-card/60 border-alpha-border hover:border-alpha-borderSubtle'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2 font-mono">
                  <span className="text-[10px] text-alpha-gold tracking-wider uppercase font-semibold">
                    v{strat.version}
                  </span>
                  {isRunning && (
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950/60 text-emerald-400 border border-emerald-800 font-bold animate-pulse">
                      LIVE IN RUNNER
                    </span>
                  )}
                </div>

                <h3 className="font-semibold text-white text-sm capitalize">
                  {strat.name}
                </h3>
                <p className="text-xs text-alpha-text-secondary mt-1.5 leading-relaxed">
                  {strat.description}
                </p>

                {/* Candidate Parameters */}
                <div className="mt-4 pt-3 border-t border-alpha-borderSubtle">
                  <span className="text-[10px] font-mono uppercase text-alpha-text-muted block mb-1">
                    Candidate Hyperparameters
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(strat.candidate_parameters).map(([k, v]) => (
                      <span
                        key={k}
                        className="px-2 py-0.5 bg-alpha-surface text-alpha-text-secondary text-[11px] font-mono rounded border border-alpha-borderSubtle"
                      >
                        {k}: <strong className="text-white">{String(v)}</strong>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Features Used */}
                <div className="mt-3">
                  <span className="text-[10px] font-mono uppercase text-alpha-text-muted block mb-1">
                    Feature Pipeline Inputs
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {strat.features_used.map((feat) => (
                      <span
                        key={feat}
                        className="px-1.5 py-0.5 bg-alpha-gold/10 text-alpha-gold text-[10px] font-mono rounded border border-alpha-gold/20"
                      >
                        {feat}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-5 pt-3 border-t border-alpha-borderSubtle flex items-center justify-between">
                <span className="text-[11px] font-mono text-alpha-text-muted">
                  {isSelected ? 'Selected for Action' : 'Click to inspect'}
                </span>
                <span className="text-alpha-gold font-mono text-xs font-semibold">
                  {isSelected ? '● ACTIVE' : 'SELECT'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Persisted Evaluation Results & Experiment Signal Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Persisted Runs History (4 cols) */}
        <div className="lg:col-span-4 bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
            <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
              Persisted Experiments ({experiments.length})
            </h3>
            <span className="text-[10px] font-mono text-alpha-text-muted">TimescaleDB</span>
          </div>

          {experiments.length === 0 ? (
            <p className="text-xs font-mono text-alpha-text-muted py-6 text-center">
              No historical evaluation experiments recorded yet.
            </p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
              {experiments.map((exp) => (
                <button
                  key={exp.id}
                  onClick={() => handleSelectExperiment(exp.id)}
                  className={`w-full text-left p-3 rounded-lg border text-xs font-mono transition-colors ${
                    activeExperiment?.id === exp.id
                      ? 'border-alpha-gold bg-alpha-gold/10 text-white'
                      : 'border-alpha-border bg-alpha-surface text-alpha-text-secondary hover:border-alpha-borderSubtle'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white capitalize">
                      {exp.strategy_id.replace('_', ' ')}
                    </span>
                    <span className="text-[10px] text-alpha-text-muted">
                      {new Date(exp.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[11px] text-alpha-text-muted">
                    <span>{exp.candle_count} candles</span>
                    <span>•</span>
                    <span className="text-emerald-400">{exp.buy_signals} Buy</span>
                    <span>•</span>
                    <span className="text-rose-400">{exp.sell_signals} Sell</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Active Experiment Signals Table (8 cols) */}
        <div className="lg:col-span-8 bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
            <div>
              <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
                Audited Signal Decisions {activeExperiment ? `(${activeExperiment.strategy_id})` : ''}
              </h3>
              {activeExperiment && (
                <p className="text-[11px] font-mono text-alpha-text-muted mt-0.5">
                  Fingerprint: {activeExperiment.dataset_fingerprint.substring(0, 16)}... | Symbol: {activeExperiment.symbol} ({activeExperiment.interval})
                </p>
              )}
            </div>

            {activeExperiment && (
              <div className="flex items-center gap-2 text-xs font-mono">
                <span className="text-emerald-400 font-bold">{activeExperiment.buy_signals} BUY</span>
                <span>/</span>
                <span className="text-rose-400 font-bold">{activeExperiment.sell_signals} SELL</span>
                <span>/</span>
                <span className="text-neutral-400">{activeExperiment.hold_signals} HOLD</span>
              </div>
            )}
          </div>

          {!activeExperiment || !activeExperiment.signals || activeExperiment.signals.length === 0 ? (
            <p className="text-xs font-mono text-alpha-text-muted py-8 text-center">
              Select an experiment from the left or trigger an evaluation to inspect chronological signals.
            </p>
          ) : (
            <div className="overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-alpha-borderSubtle text-alpha-text-muted sticky top-0 bg-alpha-card">
                    <th className="py-2 pr-3">Timestamp (UTC)</th>
                    <th className="py-2 pr-3">Side</th>
                    <th className="py-2 pr-3">Score</th>
                    <th className="py-2 pr-3">Ref Price</th>
                    <th className="py-2">Decision Reason & Features</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-alpha-borderSubtle/60 text-alpha-text-secondary">
                  {activeExperiment.signals.slice(-40).reverse().map((sig, idx) => (
                    <tr key={idx} className="hover:bg-alpha-cardHover transition-colors">
                      <td className="py-2 pr-3 text-alpha-text-muted whitespace-nowrap">
                        {new Date(sig.decision_timestamp).toISOString().replace('T', ' ').substring(0, 19)}
                      </td>
                      <td className="py-2 pr-3">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border ${
                            sig.side === 'buy'
                              ? 'bg-emerald-950/50 text-emerald-400 border-emerald-800/40'
                              : sig.side === 'sell'
                              ? 'bg-rose-950/50 text-rose-400 border-rose-800/40'
                              : 'bg-neutral-900 text-neutral-400 border-neutral-700'
                          }`}
                        >
                          {sig.side}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-white">
                        {sig.signal_score.toFixed(2)}
                      </td>
                      <td className="py-2 pr-3 font-semibold text-white">
                        ${sig.reference_price.toFixed(2)}
                      </td>
                      <td className="py-2 text-[11px]">
                        <span className="text-white block">{sig.reason}</span>
                        {sig.relevant_features && (
                          <span className="text-alpha-text-muted text-[10px]">
                            {Object.entries(sig.relevant_features)
                              .map(([k, v]) => `${k}=${v !== null ? v.toFixed(2) : 'N/A'}`)
                              .join(' | ')}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* MODAL: Confirmation for Starting Paper Execution */}
      {showStartModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-alpha-card border border-alpha-gold/40 rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-5 animate-scale-in">
            <div className="flex items-center gap-3 border-b border-alpha-borderSubtle pb-4">
              <div className="p-2 rounded-lg bg-alpha-gold/15 text-alpha-gold">
                <Play className="w-5 h-5 fill-current" />
              </div>
              <div>
                <h3 className="text-base font-bold font-mono text-white">
                  Confirm Paper Execution Launch
                </h3>
                <p className="text-xs text-alpha-text-secondary mt-0.5 font-mono">
                  Strategy: {selectedStrategy?.name}
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-lg bg-amber-950/30 border border-amber-800/50 text-amber-200 text-xs font-mono space-y-1">
              <div className="flex items-center gap-2 font-bold uppercase text-amber-300">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>Operator Risk Disclosure</span>
              </div>
              <p>
                Paper execution continuously runs the signal loop against live market bars and submits simulated orders to the PaperBroker.
              </p>
              <p className="text-amber-400 font-semibold">
                • Zero real capital or live exchange keys are touched.
                • All simulated orders pass through the 11 Central Risk Gate filters.
              </p>
            </div>

            {/* Config inputs */}
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div>
                <label className="text-alpha-text-muted block mb-1">Target Symbol</label>
                <input
                  type="text"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-1.5 text-white"
                />
              </div>

              <div>
                <label className="text-alpha-text-muted block mb-1">Bar Interval</label>
                <select
                  value={interval}
                  onChange={(e) => setInterval(e.target.value)}
                  className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-1.5 text-white"
                >
                  <option value="1m">1m Candles</option>
                  <option value="5m">5m Candles</option>
                  <option value="15m">15m Candles</option>
                </select>
              </div>

              <div>
                <label className="text-alpha-text-muted block mb-1">Order Size %</label>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  max="10.0"
                  value={orderSizePct}
                  onChange={(e) => setOrderSizePct(Number(e.target.value))}
                  className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-1.5 text-white"
                />
                <span className="text-[10px] text-alpha-text-muted">Max limit: 10%</span>
              </div>

              <div>
                <label className="text-alpha-text-muted block mb-1">Poll Interval (Sec)</label>
                <input
                  type="number"
                  step="1"
                  min="1"
                  max="60"
                  value={pollIntervalSeconds}
                  onChange={(e) => setPollIntervalSeconds(Number(e.target.value))}
                  className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-1.5 text-white"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-alpha-borderSubtle">
              <button
                type="button"
                onClick={() => setShowStartModal(false)}
                className="px-4 py-2 rounded-lg bg-alpha-surface border border-alpha-border text-xs font-mono text-alpha-text-secondary hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isStartingOrStopping}
                onClick={handleConfirmStartPaper}
                className="px-4 py-2 rounded-lg bg-alpha-gold text-black font-semibold text-xs font-mono hover:bg-alpha-gold/90 transition-colors flex items-center gap-2"
              >
                {isStartingOrStopping ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Engaging Runner...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>Confirm & Launch Paper Loop</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Confirmation for Halting Paper Execution */}
      {showStopModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-alpha-card border border-rose-900/60 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4 animate-scale-in">
            <div className="flex items-center gap-3 border-b border-alpha-borderSubtle pb-4">
              <div className="p-2 rounded-lg bg-rose-950/60 text-rose-400">
                <Square className="w-5 h-5 fill-current" />
              </div>
              <div>
                <h3 className="text-base font-bold font-mono text-white">
                  Halt Paper Execution Loop
                </h3>
                <p className="text-xs text-alpha-text-secondary mt-0.5 font-mono">
                  Release runner lock and cease automated order submission
                </p>
              </div>
            </div>

            <p className="text-xs font-mono text-alpha-text-secondary">
              Are you sure you want to stop the automated paper trading runner? Existing open positions will remain safely resting in the virtual portfolio.
            </p>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-alpha-borderSubtle">
              <button
                type="button"
                onClick={() => setShowStopModal(false)}
                className="px-4 py-2 rounded-lg bg-alpha-surface border border-alpha-border text-xs font-mono text-alpha-text-secondary hover:text-white"
              >
                Dismiss
              </button>
              <button
                type="button"
                disabled={isStartingOrStopping}
                onClick={handleConfirmStopPaper}
                className="px-4 py-2 rounded-lg bg-rose-600 text-white font-semibold text-xs font-mono hover:bg-rose-500 transition-colors flex items-center gap-2"
              >
                {isStartingOrStopping ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Draining Tasks...</span>
                  </>
                ) : (
                  <>
                    <Square className="w-3.5 h-3.5 fill-current" />
                    <span>Confirm Halt</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
