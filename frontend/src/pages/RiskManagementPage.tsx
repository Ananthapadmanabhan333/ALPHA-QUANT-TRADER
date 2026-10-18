import React, { useEffect, useState, useCallback } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  RefreshCw,
  Sliders,
  Activity,
  TrendingDown,
  DollarSign,
  Radio,
  CheckCircle,
  XCircle,
  RotateCcw,
} from 'lucide-react';
import {
  fetchRiskStatus,
  fetchSystemEvents,
  triggerEmergencyStop,
  resetRiskLimits,
} from '../services/api';
import { RiskStatus, SystemEvent } from '../types';

export const RiskManagementPage: React.FC = () => {
  const [risk, setRisk] = useState<RiskStatus | null>(null);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Emergency Stop Modal
  const [showHaltModal, setShowHaltModal] = useState<boolean>(false);
  const [haltReason, setHaltReason] = useState<string>('Operator manual intervention via Risk Console');

  // Risk Reset Modal
  const [showResetModal, setShowResetModal] = useState<boolean>(false);
  const [confirmationCode, setConfirmationCode] = useState<string>('');
  const [resetReason, setResetReason] = useState<string>('Operator authorized limit reset');
  const [resetEmergencyStop, setResetEmergencyStop] = useState<boolean>(true);
  const [resetConsecutiveLosses, setResetConsecutiveLosses] = useState<boolean>(true);
  const [resetDailyLoss, setResetDailyLoss] = useState<boolean>(false);
  const [isActionPending, setIsActionPending] = useState<boolean>(false);

  const loadRiskData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [riskRes, eventsRes] = await Promise.all([
        fetchRiskStatus('BTCUSDT').catch(() => null),
        fetchSystemEvents(severityFilter || undefined, undefined, 50, 0).catch(() => ({
          total: 0,
          limit: 50,
          offset: 0,
          items: [],
        })),
      ]);
      setRisk(riskRes);
      setEvents(eventsRes.items || []);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to query risk gate telemetry');
    } finally {
      setIsRefreshing(false);
    }
  }, [severityFilter]);

  useEffect(() => {
    loadRiskData();
    const timer = window.setInterval(loadRiskData, 4000);
    return () => clearInterval(timer);
  }, [loadRiskData]);

  const handleTriggerEmergencyStop = async () => {
    setIsActionPending(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await triggerEmergencyStop(haltReason);
      setShowHaltModal(false);
      setSuccessMsg('Emergency stop successfully triggered. All simulated entries blocked.');
      await loadRiskData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to engage emergency stop.');
    } finally {
      setIsActionPending(false);
    }
  };

  const handleResetRiskLimits = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsActionPending(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await resetRiskLimits({
        confirmation_code: confirmationCode,
        reset_emergency_stop: resetEmergencyStop,
        reset_consecutive_losses: resetConsecutiveLosses,
        reset_daily_loss: resetDailyLoss,
        reason: resetReason,
      });
      setShowResetModal(false);
      setConfirmationCode('');
      setSuccessMsg('Risk controls successfully reset by operator authorization.');
      await loadRiskData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reset risk controls.');
    } finally {
      setIsActionPending(false);
    }
  };


  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-alpha-border">
        <div>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <h1 className="text-lg sm:text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 sm:w-6 sm:h-6 text-alpha-gold shrink-0" />
              <span>CENTRAL RISK GATE & KILL-SWITCH</span>
            </h1>
            <span
              className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded border ${
                risk?.emergency_stop
                  ? 'bg-rose-950/60 text-rose-400 border-rose-800 animate-pulse'
                  : 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40'
              }`}
            >
              {risk?.emergency_stop ? 'CIRCUIT BREAKER ENGAGED' : 'SYSTEM NOMINAL (11 CHECKS)'}
            </span>
          </div>
          <p className="text-xs text-alpha-text-secondary mt-1 font-mono">
            Mandatory Pre-Trade Invariants • Peak-to-Trough Drawdown • Circuit Breaker Interlocks
          </p>
        </div>

        {/* Global Kill Switch & Reset Actions */}
        <div className="flex items-center gap-2 sm:gap-3">
          {risk?.emergency_stop ? (
            <button
              onClick={() => setShowResetModal(true)}
              className="flex-1 sm:flex-initial justify-center px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs font-mono rounded-lg transition-colors flex items-center gap-2 shadow-sm"
            >
              <RotateCcw className="w-4 h-4 shrink-0" />
              <span>Operator Reset (CONFIRM_RESET)</span>
            </button>
          ) : (
            <button
              onClick={() => setShowHaltModal(true)}
              className="flex-1 sm:flex-initial justify-center px-3.5 py-2 bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs font-mono rounded-lg transition-colors flex items-center gap-2 shadow-sm"
            >
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>Trigger Emergency Stop</span>
            </button>
          )}

          <button
            onClick={loadRiskData}
            disabled={isRefreshing}
            className="p-2 rounded-lg bg-alpha-card border border-alpha-border text-alpha-text-secondary hover:text-alpha-gold transition-colors shrink-0"
            title="Refresh Risk Telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-alpha-gold' : ''}`} />
          </button>
        </div>
      </div>

      {/* Emergency Stop Critical Alert */}
      {risk?.emergency_stop && (
        <div className="p-4 sm:p-5 rounded-xl border border-rose-900/80 bg-rose-950/60 shadow-lg text-rose-200 space-y-2">
          <div className="flex items-start sm:items-center gap-3 font-mono font-bold text-xs sm:text-sm tracking-wider">
            <XCircle className="w-5 h-5 sm:w-6 sm:h-6 text-rose-400 animate-pulse flex-shrink-0 mt-0.5 sm:mt-0" />
            <span>CIRCUIT BREAKER ACTIVE — ALL SIMULATED ORDER ENTRIES ARE HARD-BLOCKED</span>
          </div>
          <p className="text-xs font-mono text-rose-300 sm:pl-9">
            Reason: <strong className="text-white">{risk.kill_switch_reason || 'Manual emergency stop or loss limit breach.'}</strong>
          </p>
          <div className="sm:pl-9 pt-1">
            <button
              onClick={() => setShowResetModal(true)}
              className="px-3 py-1.5 rounded bg-rose-800 hover:bg-rose-700 text-white text-xs font-mono transition-colors font-semibold"
            >
              Authorize Reset Token &rarr;
            </button>
          </div>
        </div>
      )}

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

      {/* Risk Metrics Status Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {/* Drawdown Gauge */}
        <div className="p-3.5 sm:p-5 rounded-xl border border-alpha-border bg-alpha-card">
          <div className="flex items-center justify-between text-[11px] sm:text-xs text-alpha-text-muted mb-2 font-mono uppercase">
            <span>Peak Drawdown</span>
            <TrendingDown className="w-4 h-4 text-rose-400 shrink-0" />
          </div>
          <div className="text-lg sm:text-2xl font-bold font-mono text-white truncate">
            {(risk?.current_drawdown_pct ?? 0).toFixed(2)}%
          </div>
          <div className="mt-3 flex items-center justify-between text-[10px] sm:text-xs font-mono text-alpha-text-muted border-t border-alpha-borderSubtle pt-2">
            <span>Limit:</span>
            <span className="text-rose-400 font-semibold">{(risk?.max_drawdown_limit_pct ?? 5.0).toFixed(1)}%</span>
          </div>
        </div>

        {/* Daily Loss Gauge */}
        <div className="p-3.5 sm:p-5 rounded-xl border border-alpha-border bg-alpha-card">
          <div className="flex items-center justify-between text-[11px] sm:text-xs text-alpha-text-muted mb-2 font-mono uppercase">
            <span>Daily Loss P&L</span>
            <DollarSign className="w-4 h-4 text-alpha-gold shrink-0" />
          </div>
          <div className={`text-lg sm:text-2xl font-bold font-mono truncate ${(risk?.current_daily_pnl ?? 0) < 0 ? 'text-rose-400' : 'text-white'}`}>
            ${(risk?.current_daily_pnl ?? 0).toFixed(2)}
          </div>
          <div className="mt-3 flex items-center justify-between text-[10px] sm:text-xs font-mono text-alpha-text-muted border-t border-alpha-borderSubtle pt-2">
            <span>Limit:</span>
            <span className="text-rose-400 font-semibold">{(risk?.daily_loss_limit_pct ?? 2.0).toFixed(1)}%</span>
          </div>
        </div>

        {/* Consecutive Losses */}
        <div className="p-3.5 sm:p-5 rounded-xl border border-alpha-border bg-alpha-card">
          <div className="flex items-center justify-between text-[11px] sm:text-xs text-alpha-text-muted mb-2 font-mono uppercase">
            <span>Loss Streak</span>
            <Activity className="w-4 h-4 text-alpha-gold shrink-0" />
          </div>
          <div className="text-lg sm:text-2xl font-bold font-mono text-white truncate">
            {risk?.consecutive_losses ?? 0}
            <span className="text-xs text-alpha-text-muted font-normal"> / {risk?.consecutive_loss_limit ?? 5}</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[10px] sm:text-xs font-mono text-alpha-text-muted border-t border-alpha-borderSubtle pt-2">
            <span>Trip:</span>
            <span className="text-amber-400">Halt</span>
          </div>
        </div>

        {/* Feed Freshness / Status */}
        <div className="p-3.5 sm:p-5 rounded-xl border border-alpha-border bg-alpha-card">
          <div className="flex items-center justify-between text-[11px] sm:text-xs text-alpha-text-muted mb-2 font-mono uppercase">
            <span>Data Feed</span>
            <Radio className="w-4 h-4 text-alpha-gold shrink-0" />
          </div>
          <div className="text-lg sm:text-2xl font-bold font-mono text-white truncate">
            {risk?.feed_status || 'HEALTHY'}
          </div>
          <div className="mt-3 flex items-center justify-between text-[10px] sm:text-xs font-mono text-alpha-text-muted border-t border-alpha-borderSubtle pt-2">
            <span>Gate:</span>
            <span className={risk?.is_trading_allowed ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'}>
              {risk?.is_trading_allowed ? 'OPEN' : 'BLOCKED'}
            </span>
          </div>
        </div>
      </div>

      {/* 11 Configured Pre-Trade Invariant Limits */}
      <div className="p-6 rounded-xl border border-alpha-border bg-alpha-card space-y-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-alpha-borderSubtle pb-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-alpha-gold" />
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
              Institutional Risk Limits Matrix (11 Active Checks)
            </h2>
          </div>
          <span className="text-[11px] font-mono text-alpha-gold">Enforced Synchronously</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">1. Max Order Notional:</span>
              <strong className="text-white">${(risk?.max_order_notional ?? 5000).toLocaleString()} USD</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Rejects single simulated orders exceeding cap</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">2. Max Single Position %:</span>
              <strong className="text-white">{(risk?.max_position_pct ?? 10.0).toFixed(0)}% Equity</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Prevents asset concentration beyond 10%</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">3. Max Portfolio Exposure:</span>
              <strong className="text-white">{(risk?.max_portfolio_exposure_pct ?? 50.0).toFixed(0)}% Equity</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Total market exposure ceiling across assets</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">4. Daily Loss Limit %:</span>
              <strong className="text-rose-400">{(risk?.daily_loss_limit_pct ?? 2.0).toFixed(1)}% Daily Eq</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Pauses new orders if 2% lost in 24h rolling window</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">5. Peak Drawdown Limit:</span>
              <strong className="text-rose-400">{(risk?.max_drawdown_limit_pct ?? 5.0).toFixed(1)}% P-to-T</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Trips circuit breaker if peak equity drops &gt;5%</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">6. Consecutive Loss Limit:</span>
              <strong className="text-rose-400">{risk?.consecutive_loss_limit ?? 5} Fills</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Halts trading after 5 consecutive realized losses</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">7. Feed Freshness Guard:</span>
              <strong className="text-emerald-400">&lt;120s Max Lag</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Stops order submission during stale exchange feeds</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">8. Price Sanity & Outlier:</span>
              <strong className="text-emerald-400">&plusmn;10% of Mark</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Rejects limit orders placed abnormally far from book</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">9. Balance & Margin Check:</span>
              <strong className="text-emerald-400">100% Cash Covered</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Rejects orders without sufficient virtual USDT cash</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">10. Quantity Decimals:</span>
              <strong className="text-white">Min 0.0001 BTC</strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Strict precision parsing preventing micro-dust</p>
          </div>

          <div className="p-3.5 rounded-lg bg-alpha-surface border border-alpha-borderSubtle space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-alpha-text-muted">11. Circuit Breaker Kill-Switch:</span>
              <strong className={risk?.emergency_stop ? 'text-rose-400' : 'text-emerald-400'}>
                {risk?.emergency_stop ? 'ENGAGED' : 'ARMED'}
              </strong>
            </div>
            <p className="text-[10px] text-alpha-text-secondary">Immediate manual / automated trading lockout</p>
          </div>
        </div>
      </div>

      {/* Recorded Risk Events Table */}
      <div className="p-6 rounded-xl border border-alpha-border bg-alpha-card space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-alpha-borderSubtle pb-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-alpha-gold" />
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
              Recorded Risk & Audit Events ({events.length})
            </h2>
          </div>

          {/* Severity filter */}
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="text-alpha-text-muted">Filter:</span>
            {['', 'CRITICAL', 'WARNING', 'INFO'].map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`px-2 py-0.5 rounded border transition-colors ${
                  severityFilter === sev
                    ? 'bg-alpha-gold text-black font-semibold border-alpha-gold'
                    : 'bg-alpha-surface text-alpha-text-secondary border-alpha-borderSubtle hover:text-white'
                }`}
              >
                {sev || 'ALL'}
              </button>
            ))}
          </div>
        </div>

        {events.length === 0 ? (
          <p className="text-xs font-mono text-alpha-text-muted py-8 text-center">
            No risk breaches or emergency events recorded in database audit ledger.
          </p>
        ) : (
          <div className="overflow-x-auto max-h-96 overflow-y-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-alpha-borderSubtle text-alpha-text-muted sticky top-0 bg-alpha-card">
                  <th className="py-2 pr-3">Timestamp (UTC)</th>
                  <th className="py-2 pr-3">Severity</th>
                  <th className="py-2 pr-3">Event Type</th>
                  <th className="py-2 pr-3">Reason & Detail</th>
                  <th className="py-2">Audit Metadata</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-alpha-borderSubtle/60 text-alpha-text-secondary">
                {events.map((evt) => (
                  <tr key={evt.id} className="hover:bg-alpha-cardHover transition-colors">
                    <td className="py-2 pr-3 text-alpha-text-muted whitespace-nowrap">
                      {new Date(evt.created_at).toISOString().replace('T', ' ').substring(0, 19)}
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border ${
                          evt.severity === 'CRITICAL'
                            ? 'bg-rose-950/50 text-rose-400 border-rose-800/40'
                            : evt.severity === 'WARNING'
                            ? 'bg-amber-950/50 text-amber-400 border-amber-800/40'
                            : 'bg-neutral-900 text-neutral-400 border-neutral-700'
                        }`}
                      >
                        {evt.severity}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-white font-semibold whitespace-nowrap">
                      {evt.event_type}
                    </td>
                    <td className="py-2 pr-3 text-alpha-text-primary">
                      {evt.reason}
                    </td>
                    <td className="py-2 text-[11px] text-alpha-text-muted">
                      {evt.metadata_json ? JSON.stringify(evt.metadata_json) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* MODAL: Emergency Stop Confirmation */}
      {showHaltModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-alpha-card border border-rose-900/60 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4 animate-scale-in">
            <div className="flex items-center gap-3 border-b border-alpha-borderSubtle pb-4 text-rose-400">
              <ShieldAlert className="w-6 h-6" />
              <div>
                <h3 className="text-base font-bold font-mono text-white">Engage Emergency Stop</h3>
                <p className="text-xs text-rose-300 mt-0.5 font-mono">Immediate order execution lockdown</p>
              </div>
            </div>

            <p className="text-xs font-mono text-alpha-text-secondary">
              This action immediately trips the Central Risk Gate circuit breaker. All subsequent simulated order attempts will be hard-rejected with HTTP 400.
            </p>

            <div className="text-xs font-mono">
              <label className="text-alpha-text-muted block mb-1">Reason for Emergency Stop</label>
              <input
                type="text"
                value={haltReason}
                onChange={(e) => setHaltReason(e.target.value)}
                className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-1.5 text-white"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-alpha-borderSubtle">
              <button
                type="button"
                onClick={() => setShowHaltModal(false)}
                className="px-4 py-2 rounded-lg bg-alpha-surface border border-alpha-border text-xs font-mono text-alpha-text-secondary hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isActionPending}
                onClick={handleTriggerEmergencyStop}
                className="px-4 py-2 rounded-lg bg-rose-600 text-white font-bold text-xs font-mono hover:bg-rose-500 transition-colors flex items-center gap-2"
              >
                {isActionPending ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <ShieldAlert className="w-3.5 h-3.5" />
                )}
                <span>Confirm Kill-Switch</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Operator Risk Control Reset */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-alpha-card border border-alpha-gold/40 rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-4 animate-scale-in">
            <div className="flex items-center gap-3 border-b border-alpha-borderSubtle pb-4 text-emerald-400">
              <RotateCcw className="w-6 h-6" />
              <div>
                <h3 className="text-base font-bold font-mono text-white">Operator Risk Control Reset</h3>
                <p className="text-xs text-alpha-text-secondary mt-0.5 font-mono">
                  Administrative clearing of tripped risk gates
                </p>
              </div>
            </div>

            <form onSubmit={handleResetRiskLimits} className="space-y-4 text-xs font-mono">
              <p className="text-alpha-text-secondary">
                To reset tripped circuit breakers, consecutive loss counters, or daily drawdown caps, enter the administrative confirmation code{' '}
                <strong className="text-alpha-gold font-bold">CONFIRM_RESET</strong>.
              </p>

              <div>
                <label className="text-alpha-text-muted block mb-1">Confirmation Code</label>
                <input
                  type="text"
                  value={confirmationCode}
                  onChange={(e) => setConfirmationCode(e.target.value)}
                  placeholder="CONFIRM_RESET"
                  className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-2 text-white font-mono"
                />
              </div>

              <div className="space-y-2 pt-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={resetEmergencyStop}
                    onChange={(e) => setResetEmergencyStop(e.target.checked)}
                    className="rounded border-alpha-border text-alpha-gold focus:ring-alpha-gold bg-alpha-surface"
                  />
                  <span>Reset Emergency Stop Circuit Breaker</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={resetConsecutiveLosses}
                    onChange={(e) => setResetConsecutiveLosses(e.target.checked)}
                    className="rounded border-alpha-border text-alpha-gold focus:ring-alpha-gold bg-alpha-surface"
                  />
                  <span>Reset Consecutive Losses Counter (0 loss streak)</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={resetDailyLoss}
                    onChange={(e) => setResetDailyLoss(e.target.checked)}
                    className="rounded border-alpha-border text-alpha-gold focus:ring-alpha-gold bg-alpha-surface"
                  />
                  <span>Reset Daily Starting Equity Snapshot</span>
                </label>
              </div>

              <div>
                <label className="text-alpha-text-muted block mb-1">Operator Justification</label>
                <input
                  type="text"
                  value={resetReason}
                  onChange={(e) => setResetReason(e.target.value)}
                  className="w-full bg-alpha-surface border border-alpha-border rounded px-2.5 py-1.5 text-white"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-alpha-borderSubtle">
                <button
                  type="button"
                  onClick={() => setShowResetModal(false)}
                  className="px-4 py-2 rounded-lg bg-alpha-surface border border-alpha-border text-alpha-text-secondary hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={confirmationCode !== 'CONFIRM_RESET' || isActionPending}
                  className="px-4 py-2 rounded-lg bg-emerald-600 text-white font-bold hover:bg-emerald-500 transition-colors disabled:opacity-40 flex items-center gap-2"
                >
                  {isActionPending ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <RotateCcw className="w-3.5 h-3.5" />
                  )}
                  <span>Authorize Reset</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default RiskManagementPage;
