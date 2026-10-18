import React, { useEffect, useState, useCallback } from 'react';
import {
  FlaskConical,
  RefreshCw,
  Play,
  CheckCircle,
  AlertTriangle,
  FileCode,
} from 'lucide-react';
import {
  fetchExperiments,
  fetchExperimentDetails,
  fetchStrategies,
  runStrategy,
} from '../services/api';
import {
  StrategyExperiment,
  StrategyInfo,
} from '../types';

export const ExperimentsPage: React.FC = () => {
  const [experiments, setExperiments] = useState<StrategyExperiment[]>([]);
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [selectedExp, setSelectedExp] = useState<StrategyExperiment | null>(null);
  const [strategyFilter, setStrategyFilter] = useState<string>('');
  const [symbolFilter] = useState<string>('BTCUSDT');

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // New Experiment Execution Modal
  const [showRunModal, setShowRunModal] = useState<boolean>(false);
  const [modalStrategyId, setModalStrategyId] = useState<string>('trend_following');
  const [modalInterval, setModalInterval] = useState<string>('1m');
  const [modalCandleLimit, setModalCandleLimit] = useState<number>(300);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [expRes, stratList] = await Promise.all([
        fetchExperiments(strategyFilter || undefined, symbolFilter || undefined, 50).catch(() => ({
          count: 0,
          experiments: [],
        })),
        fetchStrategies().catch(() => []),
      ]);
      setExperiments(expRes.experiments || []);
      setStrategies(stratList);

      if (expRes.experiments && expRes.experiments.length > 0) {
        // Load details for first experiment if none selected
        const first = expRes.experiments[0];
        if (first && (!selectedExp || !selectedExp.signals)) {
          const detailed = await fetchExperimentDetails(first.id).catch(() => null);
          if (detailed) setSelectedExp(detailed);
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to query experiments ledger');
    } finally {
      setIsLoading(false);
    }
  }, [strategyFilter, symbolFilter, selectedExp]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSelectExperiment = async (expId: string) => {
    try {
      const detailed = await fetchExperimentDetails(expId);
      setSelectedExp(detailed);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load experiment signals');
    }
  };

  const handleLaunchExperiment = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsEvaluating(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const stratObj = strategies.find((s) => s.strategy_id === modalStrategyId);
      const res = await runStrategy({
        strategy_id: modalStrategyId,
        symbol: 'BTCUSDT',
        interval: modalInterval,
        limit: modalCandleLimit,
        parameters: stratObj?.candidate_parameters ?? {},
      });
      setShowRunModal(false);
      setSelectedExp(res);
      setSuccessMsg(`Experiment ${res.id.substring(0, 8)} executed: ${res.total_signals} signals generated.`);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Experiment execution failed');
    } finally {
      setIsEvaluating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-alpha-border">
        <div>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <h1 className="text-lg sm:text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
              <FlaskConical className="w-5 h-5 sm:w-6 sm:h-6 text-alpha-gold shrink-0" />
              <span>REPRODUCIBLE QUANT EXPERIMENTS</span>
            </h1>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-alpha-gold/10 text-alpha-gold border border-alpha-gold/30">
              AUDITED LEDGER
            </span>
          </div>
          <p className="text-xs text-alpha-text-secondary mt-1 font-mono">
            Cryptographic SHA-256 Dataset Fingerprints • Hyperparameter Tracking • Immutable Signal Logs
          </p>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <button
            onClick={() => setShowRunModal(true)}
            className="flex-1 sm:flex-initial justify-center px-3.5 py-2 bg-alpha-gold hover:bg-alpha-gold/90 text-black font-semibold text-xs font-mono rounded-lg transition-colors flex items-center gap-2 shadow-sm"
          >
            <Play className="w-3.5 h-3.5 fill-current shrink-0" />
            <span>New Experiment</span>
          </button>

          <button
            onClick={loadData}
            disabled={isLoading}
            className="p-2 rounded-lg bg-alpha-card border border-alpha-border text-alpha-text-secondary hover:text-alpha-gold transition-colors shrink-0"
            title="Refresh Experiments"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-alpha-gold' : ''}`} />
          </button>
        </div>
      </div>

      {/* Notices */}
      {successMsg && (
        <div className="p-4 rounded-xl border border-emerald-900/60 bg-emerald-950/30 flex items-start gap-3 text-emerald-300 text-xs font-mono">
          <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl border border-rose-900/60 bg-rose-950/30 flex items-start gap-3 text-rose-300 text-xs font-mono">
          <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Grid: Experiments List (Left) & Experiment Inspector (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Experiments Catalog (4 cols) */}
        <div className="lg:col-span-4 bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
              Historical Runs ({experiments.length})
            </h2>

            {/* Filter */}
            <select
              value={strategyFilter}
              onChange={(e) => setStrategyFilter(e.target.value)}
              className="bg-alpha-surface border border-alpha-border text-[11px] font-mono text-alpha-text-secondary rounded px-2 py-1"
            >
              <option value="">All Strategies</option>
              {strategies.map((s) => (
                <option key={s.strategy_id} value={s.strategy_id}>
                  {s.strategy_id}
                </option>
              ))}
            </select>
          </div>

          {experiments.length === 0 ? (
            <p className="text-xs font-mono text-alpha-text-muted py-8 text-center">
              No experiments recorded yet. Launch an evaluation using the &quot;New Experiment&quot; button.
            </p>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {experiments.map((exp) => (
                <button
                  key={exp.id}
                  onClick={() => handleSelectExperiment(exp.id)}
                  className={`w-full text-left p-3 rounded-lg border text-xs font-mono transition-colors ${
                    selectedExp?.id === exp.id
                      ? 'border-alpha-gold bg-alpha-gold/10'
                      : 'border-alpha-border bg-alpha-surface hover:border-alpha-borderSubtle'
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

                  <div className="mt-1 flex items-center justify-between text-[11px] text-alpha-text-muted">
                    <span>{exp.candle_count} candles ({exp.interval})</span>
                    <span className="text-alpha-gold">{exp.total_signals} signals</span>
                  </div>

                  <div className="mt-1 text-[10px] text-alpha-text-muted truncate">
                    SHA: {exp.dataset_fingerprint.substring(0, 16)}...
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Experiment Metadata & Signals Log (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {!selectedExp ? (
            <div className="p-12 text-center rounded-xl border border-alpha-border bg-alpha-card">
              <FlaskConical className="w-8 h-8 text-alpha-gold mx-auto mb-2 opacity-50" />
              <p className="text-xs font-mono text-alpha-text-muted">
                Select an experiment from the left column to inspect reproducible parameters and signal logs.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Metadata Dossier Card */}
              <div className="p-6 rounded-xl border border-alpha-border bg-alpha-card shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-alpha-borderSubtle pb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-alpha-gold/15 text-alpha-gold rounded border border-alpha-gold/30">
                        v{selectedExp.strategy_version}
                      </span>
                      <h2 className="text-lg font-bold font-mono text-white capitalize">
                        {selectedExp.strategy_id.replace('_', ' ')} Experiment
                      </h2>
                    </div>
                    <p className="text-xs text-alpha-text-secondary mt-1 font-mono">
                      Experiment ID: {selectedExp.id}
                    </p>
                  </div>

                  <div className="text-right">
                    <span className="text-[10px] font-mono text-alpha-text-muted uppercase block">Signal Balance</span>
                    <div className="flex items-center gap-2 text-xs font-mono mt-0.5">
                      <span className="text-emerald-400 font-bold">{selectedExp.buy_signals} BUY</span>
                      <span>/</span>
                      <span className="text-rose-400 font-bold">{selectedExp.sell_signals} SELL</span>
                      <span>/</span>
                      <span className="text-neutral-400">{selectedExp.hold_signals} HOLD</span>
                    </div>
                  </div>
                </div>

                {/* Reproducibility Metadata Bar */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
                  <div className="p-3 bg-alpha-surface border border-alpha-borderSubtle rounded-lg">
                    <span className="text-[10px] uppercase text-alpha-text-muted block">SHA-256 Dataset Fingerprint</span>
                    <p className="font-mono text-alpha-gold mt-1 truncate" title={selectedExp.dataset_fingerprint}>
                      {selectedExp.dataset_fingerprint}
                    </p>
                  </div>

                  <div className="p-3 bg-alpha-surface border border-alpha-borderSubtle rounded-lg">
                    <span className="text-[10px] uppercase text-alpha-text-muted block">Observation Window</span>
                    <p className="text-white mt-1">
                      {selectedExp.candle_count} bars ({selectedExp.symbol} {selectedExp.interval})
                    </p>
                  </div>

                  <div className="p-3 bg-alpha-surface border border-alpha-borderSubtle rounded-lg">
                    <span className="text-[10px] uppercase text-alpha-text-muted block">Timestamp Alignment</span>
                    <p className="text-white mt-1">
                      {new Date(selectedExp.time_range_start).toISOString().substring(11, 16)} &rarr; {new Date(selectedExp.time_range_end).toISOString().substring(11, 16)} UTC
                    </p>
                  </div>
                </div>

                {/* Parameters Matrix */}
                <div className="pt-2">
                  <span className="text-[10px] font-mono uppercase text-alpha-text-muted block mb-1.5">
                    Reproducible Hyperparameters
                  </span>
                  <div className="flex flex-wrap gap-2 text-xs font-mono">
                    {Object.entries(selectedExp.parameters).map(([k, v]) => (
                      <span
                        key={k}
                        className="px-2.5 py-1 bg-alpha-surface border border-alpha-borderSubtle rounded text-alpha-text-secondary"
                      >
                        {k}: <strong className="text-white">{String(v)}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Signals Log Table */}
              <div className="p-6 rounded-xl border border-alpha-border bg-alpha-card shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
                  <div className="flex items-center gap-2">
                    <FileCode className="w-4 h-4 text-alpha-gold" />
                    <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
                      Chronological Signals Log ({selectedExp.signals?.length ?? 0} Observations)
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono text-alpha-text-muted">
                    Immutable Audit Trail
                  </span>
                </div>

                {!selectedExp.signals || selectedExp.signals.length === 0 ? (
                  <p className="text-xs font-mono text-alpha-text-muted py-6 text-center">
                    No signals generated during this experiment observation window.
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
                        {selectedExp.signals.map((sig, idx) => (
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
          )}
        </div>
      </div>

      {/* MODAL: Launch New Experiment */}
      {showRunModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-alpha-card border border-alpha-gold/40 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4 animate-scale-in">
            <div className="flex items-center gap-3 border-b border-alpha-borderSubtle pb-4">
              <FlaskConical className="w-6 h-6 text-alpha-gold" />
              <div>
                <h3 className="text-base font-bold font-mono text-white">Launch Reproducible Experiment</h3>
                <p className="text-xs text-alpha-text-secondary mt-0.5 font-mono">
                  Compute features, generate signals, and persist dataset hash
                </p>
              </div>
            </div>

            <form onSubmit={handleLaunchExperiment} className="space-y-4 text-xs font-mono">
              <div>
                <label className="text-alpha-text-muted block mb-1">Target Strategy</label>
                <select
                  value={modalStrategyId}
                  onChange={(e) => setModalStrategyId(e.target.value)}
                  className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-2 text-white"
                >
                  {strategies.map((s) => (
                    <option key={s.strategy_id} value={s.strategy_id}>
                      {s.name} (v{s.version})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-alpha-text-muted block mb-1">Interval</label>
                  <select
                    value={modalInterval}
                    onChange={(e) => setModalInterval(e.target.value)}
                    className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-1.5 text-white"
                  >
                    <option value="1m">1m Candles</option>
                    <option value="5m">5m Candles</option>
                    <option value="15m">15m Candles</option>
                  </select>
                </div>

                <div>
                  <label className="text-alpha-text-muted block mb-1">Candles Count</label>
                  <input
                    type="number"
                    min="50"
                    max="1000"
                    step="50"
                    value={modalCandleLimit}
                    onChange={(e) => setModalCandleLimit(Number(e.target.value))}
                    className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-1.5 text-white"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-alpha-borderSubtle">
                <button
                  type="button"
                  onClick={() => setShowRunModal(false)}
                  className="px-4 py-2 rounded-lg bg-alpha-surface border border-alpha-border text-alpha-text-secondary hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isEvaluating}
                  className="px-4 py-2 rounded-lg bg-alpha-gold text-black font-semibold hover:bg-alpha-gold/90 transition-colors flex items-center gap-2"
                >
                  {isEvaluating ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-current" />
                  )}
                  <span>Run Experiment</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExperimentsPage;
