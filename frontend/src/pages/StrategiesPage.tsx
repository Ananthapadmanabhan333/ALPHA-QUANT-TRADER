import React, { useState, useEffect } from 'react';
import {
  fetchStrategies,
  runStrategy,
  fetchExperiments,
  fetchExperimentDetails,
} from '../services/api';
import {
  StrategyInfo,
  StrategyExperiment,
  StrategySignal,
} from '../types';

export const StrategiesPage: React.FC = () => {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>('trend_following');
  const [experiments, setExperiments] = useState<StrategyExperiment[]>([]);
  const [activeExperiment, setActiveExperiment] = useState<StrategyExperiment | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [executing, setExecuting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load strategies and past experiments
  useEffect(() => {
    async function loadInitialData() {
      setLoading(true);
      setError(null);
      try {
        const [stratData, expData] = await Promise.all([
          fetchStrategies(),
          fetchExperiments().catch(() => ({ count: 0, experiments: [] })),
        ]);
        setStrategies(stratData);
        const expList = expData.experiments || [];
        setExperiments(expList);
        if (expList.length > 0 && expList[0]) {
          // Load details of the newest experiment
          const newest = await fetchExperimentDetails(expList[0].id);
          setActiveExperiment(newest);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to load strategy data';
        setError(msg);
      } finally {
        setLoading(false);
      }
    }
    loadInitialData();
  }, []);

  const handleRunStrategy = async (strategyId: string) => {
    setExecuting(true);
    setError(null);
    try {
      const exp = await runStrategy({
        strategy_id: strategyId,
        symbol: 'BTCUSDT',
        interval: '1m',
        limit: 300,
      });
      setActiveExperiment(exp);
      // Refresh experiments list
      const expList = await fetchExperiments();
      setExperiments(expList.experiments || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Strategy execution failed';
      setError(msg);
    } finally {
      setExecuting(false);
    }
  };

  const handleInspectExperiment = async (expId: string) => {
    setLoading(true);
    setError(null);
    try {
      const exp = await fetchExperimentDetails(expId);
      setActiveExperiment(exp);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load experiment details';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white font-mono">
              QUANTITATIVE STRATEGIES
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
              Phase 3 Active
            </span>
            {loading && (
              <span className="text-xs font-mono text-neutral-400 flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
                Loading ledger...
              </span>
            )}
          </div>
          <p className="text-sm text-neutral-400 mt-1">
            Zero order execution • Auditable signal generation • Cryptographic dataset fingerprinting
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => handleRunStrategy(selectedStrategyId)}
            disabled={executing}
            className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-black font-semibold text-xs rounded transition flex items-center gap-2 disabled:opacity-50"
          >
            {executing ? (
              <>
                <span className="w-3 h-3 border-2 border-black/40 border-t-black rounded-full animate-spin" />
                Evaluating Signals...
              </>
            ) : (
              <>Run {selectedStrategyId.replace('_', ' ').toUpperCase()}</>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-500/30 rounded-lg text-red-300 text-sm flex items-start gap-3">
          <span className="text-red-400 text-lg">⚠️</span>
          <div>
            <div className="font-semibold text-white">Execution / Data Notice</div>
            <div className="text-xs text-red-300/90 mt-0.5">{error}</div>
          </div>
        </div>
      )}

      {/* Baseline Strategy Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {strategies.map((strat) => {
          const isSelected = selectedStrategyId === strat.strategy_id;
          return (
            <div
              key={strat.strategy_id}
              onClick={() => setSelectedStrategyId(strat.strategy_id)}
              className={`p-5 rounded-xl border transition cursor-pointer flex flex-col justify-between ${
                isSelected
                  ? 'bg-neutral-900/90 border-amber-500/60 shadow-lg shadow-amber-500/5'
                  : 'bg-neutral-900/40 border-neutral-800/80 hover:border-neutral-700'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs text-amber-400 tracking-wider uppercase">
                    v{strat.version}
                  </span>
                  {isSelected && (
                    <span className="w-2 h-2 rounded-full bg-amber-400 shadow-sm shadow-amber-400" />
                  )}
                </div>
                <h3 className="font-semibold text-white text-base leading-snug">{strat.name}</h3>
                <p className="text-xs text-neutral-400 mt-2 line-clamp-2 leading-relaxed">
                  {strat.description}
                </p>

                <div className="mt-4 pt-3 border-t border-neutral-800">
                  <div className="text-[11px] font-mono text-neutral-400 uppercase tracking-wider mb-1.5">
                    Features Used:
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {strat.features_used.map((feat) => (
                      <span
                        key={feat}
                        className="px-2 py-0.5 text-[10px] font-mono bg-neutral-800/80 text-neutral-300 rounded border border-neutral-700/50"
                      >
                        {feat}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-5 pt-3 border-t border-neutral-800/60 flex items-center justify-between text-xs">
                <span className="text-neutral-500">Long-only spot</span>
                <span className="text-amber-400 font-medium">Select & Run →</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Active Experiment Inspection */}
      {activeExperiment ? (
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl overflow-hidden shadow-xl">
          {/* Experiment Meta Top Bar */}
          <div className="p-6 border-b border-neutral-800 bg-neutral-950/40">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2.5">
                  <span className="px-2 py-0.5 text-xs font-mono font-bold bg-amber-500 text-black rounded">
                    EXPERIMENT
                  </span>
                  <span className="font-mono text-xs text-neutral-400">
                    ID: {activeExperiment.id.slice(0, 8)}...
                  </span>
                  <span className="font-mono text-xs text-neutral-500">
                    Config: {activeExperiment.config_id}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-white mt-1.5 font-mono">
                  {activeExperiment.strategy_id.toUpperCase()} • {activeExperiment.symbol} (
                  {activeExperiment.interval})
                </h2>
              </div>

              {/* Signals summary badges */}
              <div className="flex items-center gap-3">
                <div className="px-3 py-1.5 bg-neutral-900 rounded-lg border border-neutral-800 text-center">
                  <div className="text-[10px] text-neutral-400 uppercase font-mono">Total</div>
                  <div className="text-sm font-bold text-white font-mono">
                    {activeExperiment.total_signals}
                  </div>
                </div>
                <div className="px-3 py-1.5 bg-emerald-950/40 rounded-lg border border-emerald-500/30 text-center">
                  <div className="text-[10px] text-emerald-400 uppercase font-mono">Buy Signals</div>
                  <div className="text-sm font-bold text-emerald-400 font-mono">
                    {activeExperiment.buy_signals}
                  </div>
                </div>
                <div className="px-3 py-1.5 bg-red-950/40 rounded-lg border border-red-500/30 text-center">
                  <div className="text-[10px] text-red-400 uppercase font-mono">Sell Signals</div>
                  <div className="text-sm font-bold text-red-400 font-mono">
                    {activeExperiment.sell_signals}
                  </div>
                </div>
                <div className="px-3 py-1.5 bg-neutral-800/40 rounded-lg border border-neutral-700/30 text-center">
                  <div className="text-[10px] text-neutral-400 uppercase font-mono">Hold</div>
                  <div className="text-sm font-bold text-neutral-300 font-mono">
                    {activeExperiment.hold_signals}
                  </div>
                </div>
              </div>
            </div>

            {/* Cryptographic Fingerprint banner */}
            <div className="mt-4 p-3 bg-black/40 border border-neutral-800 rounded-lg flex flex-col md:flex-row md:items-center justify-between text-xs font-mono gap-2 text-neutral-400">
              <div className="flex items-center gap-2 overflow-hidden text-ellipsis">
                <span className="text-amber-500 font-semibold">DATASET SHA-256:</span>
                <span className="text-neutral-300 truncate">{activeExperiment.dataset_fingerprint}</span>
              </div>
              <div className="text-neutral-500 whitespace-nowrap">
                Range: {new Date(activeExperiment.time_range_start).toLocaleTimeString()} -{' '}
                {new Date(activeExperiment.time_range_end).toLocaleTimeString()} (
                {activeExperiment.candle_count} bars)
              </div>
            </div>
          </div>

          {/* Generated Signals Table */}
          <div className="p-6">
            <h3 className="text-sm font-mono text-neutral-300 uppercase tracking-wider mb-4 flex items-center justify-between">
              <span>Auditable Signal Ledger ({activeExperiment.signals?.length || 0} observations)</span>
              <span className="text-xs text-neutral-500 lowercase">non-executing decision stream</span>
            </h3>

            {activeExperiment.signals && activeExperiment.signals.length > 0 ? (
              <div className="overflow-x-auto max-h-96 overflow-y-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="sticky top-0 bg-neutral-900 border-b border-neutral-800 text-neutral-400 uppercase tracking-wider">
                    <tr>
                      <th className="py-2.5 px-3">Timestamp (UTC)</th>
                      <th className="py-2.5 px-3">Decision</th>
                      <th className="py-2.5 px-3">Score</th>
                      <th className="py-2.5 px-3">Ref Price</th>
                      <th className="py-2.5 px-3">Reason</th>
                      <th className="py-2.5 px-3">Features</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-800/60">
                    {activeExperiment.signals.map((sig: StrategySignal, idx: number) => {
                      const side = (sig.side || '').toLowerCase();
                      const sideClass =
                        side === 'buy'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : side === 'sell'
                          ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                          : 'bg-neutral-800 text-neutral-400 border border-neutral-700';

                      return (
                        <tr key={idx} className="hover:bg-white/[0.02]">
                          <td className="py-2 px-3 text-neutral-400 whitespace-nowrap">
                            {new Date(sig.decision_timestamp).toISOString().replace('T', ' ').slice(0, 19)}
                          </td>
                          <td className="py-2 px-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${sideClass}`}>
                              {side.toUpperCase()}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-neutral-300">
                            {sig.signal_score > 0 ? `+${sig.signal_score.toFixed(2)}` : sig.signal_score.toFixed(2)}
                          </td>
                          <td className="py-2 px-3 text-neutral-200">
                            ${sig.reference_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-2 px-3 text-neutral-300 max-w-xs truncate" title={sig.reason}>
                            {sig.reason}
                          </td>
                          <td className="py-2 px-3 text-neutral-500 text-[11px] truncate max-w-xs">
                            {JSON.stringify(sig.relevant_features)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-neutral-500 font-mono text-xs">
                No signal stream loaded for this experiment.
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Honest empty state */
        <div className="p-12 text-center border border-neutral-800 rounded-xl bg-neutral-900/30">
          <div className="w-12 h-12 mx-auto rounded-full bg-neutral-800 flex items-center justify-center text-amber-400 mb-3 text-xl">
            ⚗️
          </div>
          <h3 className="font-semibold text-white text-base">No Quantitative Experiment Run Yet</h3>
          <p className="text-xs text-neutral-400 max-w-md mx-auto mt-1 leading-relaxed">
            Select one of the baseline quantitative strategies above and click "Run" to evaluate historical candles,
            compute mathematical features, and generate auditable signals with zero order execution.
          </p>
        </div>
      )}

      {/* Historical Experiments Ledger */}
      {experiments.length > 0 && (
        <div className="bg-neutral-900/40 border border-neutral-800 rounded-xl p-6">
          <h3 className="text-sm font-mono text-neutral-300 uppercase tracking-wider mb-4">
            Recorded Experiments Ledger ({experiments.length})
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-neutral-900/80 border-b border-neutral-800 text-neutral-400 uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-3">Date (UTC)</th>
                  <th className="py-2.5 px-3">Strategy</th>
                  <th className="py-2.5 px-3">Pair / Interval</th>
                  <th className="py-2.5 px-3">Dataset Fingerprint</th>
                  <th className="py-2.5 px-3">Signals (B / S / H)</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/40">
                {experiments.map((exp) => (
                  <tr key={exp.id} className="hover:bg-white/[0.02]">
                    <td className="py-2 px-3 text-neutral-400 whitespace-nowrap">
                      {new Date(exp.created_at).toISOString().replace('T', ' ').slice(0, 19)}
                    </td>
                    <td className="py-2 px-3 font-semibold text-white">
                      {exp.strategy_id}
                    </td>
                    <td className="py-2 px-3 text-neutral-300">
                      {exp.symbol} ({exp.interval})
                    </td>
                    <td className="py-2 px-3 text-neutral-500 font-mono text-[11px]">
                      {exp.dataset_fingerprint.slice(0, 16)}...
                    </td>
                    <td className="py-2 px-3">
                      <span className="text-emerald-400 font-bold">{exp.buy_signals}</span> /{' '}
                      <span className="text-red-400 font-bold">{exp.sell_signals}</span> /{' '}
                      <span className="text-neutral-400">{exp.hold_signals}</span>
                    </td>
                    <td className="py-2 px-3 text-right">
                      <button
                        onClick={() => handleInspectExperiment(exp.id)}
                        className="px-2.5 py-1 text-[11px] font-semibold text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 rounded border border-amber-500/30 transition"
                      >
                        Inspect
                      </button>
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
