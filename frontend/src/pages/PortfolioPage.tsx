import React, { useState, useEffect } from 'react';
import {
  Briefcase,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Play,
  RefreshCw,
  DollarSign,
  Layers,
  CheckCircle,
} from 'lucide-react';
import {
  PaperAccount,
  PaperOrder,
  PaperOrderCreateRequest,
  RiskStatus,
} from '../types';
import {
  fetchPaperAccount,
  fetchPaperOrders,
  submitPaperOrder,
  cancelPaperOrder,
  fetchRiskStatus,
  triggerEmergencyStop,
  resumeEmergencyStop,
} from '../services/api';

export const PortfolioPage: React.FC = () => {
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [risk, setRisk] = useState<RiskStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Order form state
  const [orderSide, setOrderSide] = useState<'buy' | 'sell'>('buy');
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [symbol] = useState<string>('BTCUSDT');
  const [quantity, setQuantity] = useState<number>(0.01);
  const [price, setPrice] = useState<number>(50000);

  // Resume modal state
  const [showResumeModal, setShowResumeModal] = useState<boolean>(false);
  const [resumeToken, setResumeToken] = useState<string>('');

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [acc, orderList, riskStat] = await Promise.all([
        fetchPaperAccount().catch(() => null),
        fetchPaperOrders().catch(() => []),
        fetchRiskStatus().catch(() => null),
      ]);
      setAccount(acc);
      setOrders(orderList);
      setRisk(riskStat);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load paper broker data.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOrderSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setSuccessMsg(null);

    const payload: PaperOrderCreateRequest = {
      symbol,
      side: orderSide,
      order_type: orderType,
      quantity,
      price: orderType === 'limit' ? price : undefined,
    };

    try {
      const result = await submitPaperOrder(payload);
      setSuccessMsg(`Simulated order submitted: ${result.side.toUpperCase()} ${result.quantity} ${result.symbol} [${result.status.toUpperCase()}]`);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Order submission failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelOrder = async (orderId: string) => {
    try {
      await cancelPaperOrder(orderId);
      setSuccessMsg(`Order ${orderId.substring(0, 8)} cancelled successfully.`);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to cancel order.');
    }
  };

  const handleTriggerHalt = async () => {
    if (!window.confirm('Trigger Emergency Stop? This halts all simulated new entry orders immediately.')) {
      return;
    }
    try {
      await triggerEmergencyStop('Manual operator intervention from Web UI');
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to trigger emergency halt.');
    }
  };

  const handleResume = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await resumeEmergencyStop(resumeToken, true);
      setShowResumeModal(false);
      setResumeToken('');
      setSuccessMsg('Emergency halt cleared. Pre-trade risk controls remain active.');
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to resume trading.');
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-alpha-text-primary flex items-center gap-3">
            <Briefcase className="w-6 h-6 text-alpha-gold" />
            <span>Paper Execution & Central Risk Control</span>
          </h1>
          <p className="text-sm text-alpha-text-secondary mt-1">
            Simulated Spot Inventory, Pre-Trade Risk Gate, Ledger Invariants & Automated Emergency Halt
          </p>
        </div>
        <div className="flex items-center gap-3">
          {risk?.emergency_stop ? (
            <button
              onClick={() => setShowResumeModal(true)}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30 transition-colors"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Resume Operations</span>
            </button>
          ) : (
            <button
              onClick={handleTriggerHalt}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30 transition-colors"
            >
              <ShieldAlert className="w-4 h-4" />
              <span>Emergency Halt</span>
            </button>
          )}

          <button
            onClick={loadData}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg border border-alpha-border bg-alpha-surface text-alpha-text-secondary hover:text-alpha-gold hover:border-alpha-gold transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Emergency Stop Alert Banner */}
      {risk?.emergency_stop && (
        <div className="p-4 bg-rose-500/15 border border-rose-500/40 rounded-xl flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-bold text-rose-300 uppercase tracking-wide">Emergency Halt Active</h4>
              <p className="text-xs text-rose-300/90 mt-0.5">
                {risk.kill_switch_reason || 'Simulated trading is currently paused. All new entry orders are strictly rejected.'}
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowResumeModal(true)}
            className="px-3 py-1 text-xs font-bold rounded bg-rose-500 text-white hover:bg-rose-600 transition-colors"
          >
            Clear Halt
          </button>
        </div>
      )}

      {/* Status Notifications */}
      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-rose-300">Action Refused</h4>
            <p className="text-xs text-rose-400/90 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {successMsg && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-emerald-300">Execution Update</h4>
            <p className="text-xs text-emerald-400/90 mt-0.5">{successMsg}</p>
          </div>
        </div>
      )}

      {/* Account KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-alpha-card border border-alpha-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary">Virtual Cash</span>
            <DollarSign className="w-4 h-4 text-alpha-gold" />
          </div>
          <p className="text-2xl font-mono font-bold text-alpha-text-primary mt-2">
            ${(account?.virtual_balance ?? 10000).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-[11px] text-alpha-text-secondary mt-1">USDT Available</p>
        </div>

        <div className="bg-alpha-card border border-alpha-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary">Total Equity</span>
            <Layers className="w-4 h-4 text-alpha-gold" />
          </div>
          <p className="text-2xl font-mono font-bold text-alpha-text-primary mt-2">
            ${(account?.total_equity ?? 10000).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-[11px] text-alpha-text-secondary mt-1">Cash + Inventory Value</p>
        </div>

        <div className="bg-alpha-card border border-alpha-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary">Realized P&L</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <p className={`text-2xl font-mono font-bold mt-2 ${(account?.realized_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            ${(account?.realized_pnl ?? 0) >= 0 ? '+' : ''}{(account?.realized_pnl ?? 0).toFixed(2)}
          </p>
          <p className="text-[11px] text-alpha-text-secondary mt-1">Post Fees & Slippage</p>
        </div>

        <div className="bg-alpha-card border border-alpha-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary">Unrealized P&L</span>
            <TrendingDown className="w-4 h-4 text-alpha-gold" />
          </div>
          <p className={`text-2xl font-mono font-bold mt-2 ${(account?.unrealized_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            ${(account?.unrealized_pnl ?? 0) >= 0 ? '+' : ''}{(account?.unrealized_pnl ?? 0).toFixed(2)}
          </p>
          <p className="text-[11px] text-alpha-text-secondary mt-1">Mark-to-Market Valuation</p>
        </div>
      </div>

      {/* Central Risk Gate Telemetry Bar */}
      {risk && (
        <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-alpha-border pb-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-alpha-gold" />
              <span>Central Pre-Trade Risk Gate Telemetry</span>
            </h3>
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded border ${
                risk.feed_status === 'HEALTHY'
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                  : 'bg-amber-500/20 text-amber-400 border-amber-500/40'
              }`}>
                Feed: {risk.feed_status}
              </span>
              <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded border ${
                risk.is_trading_allowed
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                  : 'bg-rose-500/20 text-rose-400 border-rose-500/40'
              }`}>
                {risk.is_trading_allowed ? 'Entries Permitted' : 'Entries Blocked'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
            <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
              <span className="text-alpha-text-secondary">Current Drawdown</span>
              <p className={`text-base font-bold mt-1 ${risk.current_drawdown_pct >= risk.max_drawdown_limit_pct ? 'text-rose-400' : 'text-alpha-text-primary'}`}>
                {risk.current_drawdown_pct.toFixed(2)}%
              </p>
              <span className="text-[10px] text-alpha-text-secondary">Limit: {risk.max_drawdown_limit_pct.toFixed(1)}%</span>
            </div>

            <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
              <span className="text-alpha-text-secondary">Daily Loss P&L</span>
              <p className="text-base font-bold text-alpha-text-primary mt-1">
                ${risk.current_daily_pnl.toFixed(2)}
              </p>
              <span className="text-[10px] text-alpha-text-secondary">Limit: {risk.daily_loss_limit_pct.toFixed(1)}%</span>
            </div>

            <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
              <span className="text-alpha-text-secondary">Loss Streak</span>
              <p className={`text-base font-bold mt-1 ${risk.consecutive_losses >= risk.consecutive_loss_limit ? 'text-rose-400' : 'text-alpha-text-primary'}`}>
                {risk.consecutive_losses} loss trades
              </p>
              <span className="text-[10px] text-alpha-text-secondary">Limit: {risk.consecutive_loss_limit} consecutive</span>
            </div>

            <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
              <span className="text-alpha-text-secondary">Max Limits</span>
              <p className="text-base font-bold text-alpha-gold mt-1">
                {risk.max_position_pct.toFixed(0)}% pos / ${risk.max_order_notional.toLocaleString()}
              </p>
              <span className="text-[10px] text-alpha-text-secondary">Max Exp: {risk.max_portfolio_exposure_pct.toFixed(0)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Main Execution Grid: Order Entry Form & Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Simulated Order Launcher */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm">
            <h2 className="text-base font-semibold text-alpha-text-primary flex items-center gap-2 mb-4">
              <Play className="w-4 h-4 text-alpha-gold" />
              <span>Submit Simulated Order</span>
            </h2>

            <form onSubmit={handleOrderSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setOrderSide('buy')}
                  className={`py-2 text-xs font-bold rounded-lg border transition-colors ${
                    orderSide === 'buy'
                      ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500'
                      : 'bg-alpha-surface text-alpha-text-secondary border-alpha-border hover:border-alpha-gold/40'
                  }`}
                >
                  BUY SPOT
                </button>
                <button
                  type="button"
                  onClick={() => setOrderSide('sell')}
                  className={`py-2 text-xs font-bold rounded-lg border transition-colors ${
                    orderSide === 'sell'
                      ? 'bg-rose-500/20 text-rose-400 border-rose-500'
                      : 'bg-alpha-surface text-alpha-text-secondary border-alpha-border hover:border-alpha-gold/40'
                  }`}
                >
                  SELL SPOT
                </button>
              </div>

              <div>
                <label className="block text-xs font-semibold text-alpha-text-secondary mb-1">
                  Order Type
                </label>
                <select
                  value={orderType}
                  onChange={(e) => setOrderType(e.target.value as 'market' | 'limit')}
                  className="w-full bg-alpha-surface border border-alpha-border rounded-lg px-3 py-2 text-xs text-alpha-text-primary focus:outline-none focus:border-alpha-gold"
                >
                  <option value="market">Market Order (Immediate fill @ next price)</option>
                  <option value="limit">Limit Order (Resting order in book)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-alpha-text-secondary mb-1">
                  Quantity ({symbol.replace('USDT', '')})
                </label>
                <input
                  type="number"
                  step="0.001"
                  min="0.0001"
                  value={quantity}
                  onChange={(e) => setQuantity(Number(e.target.value))}
                  className="w-full bg-alpha-surface border border-alpha-border rounded-lg px-3 py-2 text-xs text-alpha-text-primary font-mono focus:outline-none focus:border-alpha-gold"
                />
              </div>

              {orderType === 'limit' && (
                <div>
                  <label className="block text-xs font-semibold text-alpha-text-secondary mb-1">
                    Limit Price ($ USD)
                  </label>
                  <input
                    type="number"
                    step="1"
                    min="1"
                    value={price}
                    onChange={(e) => setPrice(Number(e.target.value))}
                    className="w-full bg-alpha-surface border border-alpha-border rounded-lg px-3 py-2 text-xs text-alpha-text-primary font-mono focus:outline-none focus:border-alpha-gold"
                  />
                </div>
              )}

              <div className="p-3 bg-alpha-surface border border-alpha-border rounded-lg text-[11px] text-alpha-text-secondary space-y-1">
                <div className="flex justify-between">
                  <span>Estimated Notional:</span>
                  <span className="font-mono text-alpha-text-primary font-semibold">
                    ${(quantity * (orderType === 'limit' ? price : 50050)).toFixed(2)} USD
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Fee / Slippage Drag:</span>
                  <span className="font-mono text-alpha-text-secondary">
                    {orderType === 'market' ? '10 bps fee + 5 bps slip' : '8 bps maker fee'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Risk Concentration Cap:</span>
                  <span className="font-mono text-alpha-gold">10.0% of virtual equity</span>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting || (risk?.emergency_stop && orderSide === 'buy')}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-alpha-gold text-black hover:bg-alpha-gold/90 transition-colors disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Validating Pre-Trade Invariants...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    <span>Submit Simulated {orderSide.toUpperCase()}</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Positions & Orders Audit Log */}
        <div className="lg:col-span-7 space-y-6">
          {/* Open Positions Card */}
          <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary mb-3 flex items-center justify-between">
              <span>Simulated Spot Inventory ({account?.positions.length ?? 0})</span>
            </h3>

            {!account?.positions || account.positions.length === 0 ? (
              <p className="text-xs text-alpha-text-secondary py-4 text-center">
                No active spot positions. Account is 100% in virtual cash.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="border-b border-alpha-border text-alpha-text-secondary">
                      <th className="text-left pb-2">Asset</th>
                      <th className="text-right pb-2">Quantity</th>
                      <th className="text-right pb-2">Entry Price</th>
                      <th className="text-right pb-2">Market Val</th>
                      <th className="text-right pb-2">Unrealized P&L</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-alpha-border/40">
                    {account.positions.map((p) => (
                      <tr key={p.symbol} className="hover:bg-alpha-surface/50">
                        <td className="py-2.5 font-bold text-alpha-text-primary">{p.symbol}</td>
                        <td className="py-2.5 text-right text-alpha-text-secondary">{p.quantity.toFixed(4)}</td>
                        <td className="py-2.5 text-right text-alpha-text-secondary">${p.avg_entry_price.toFixed(2)}</td>
                        <td className="py-2.5 text-right text-alpha-text-primary">${p.market_value.toFixed(2)}</td>
                        <td className={`py-2.5 text-right font-bold ${p.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          ${p.unrealized_pnl >= 0 ? '+' : ''}{p.unrealized_pnl.toFixed(2)} ({p.unrealized_pnl_pct.toFixed(2)}%)
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Orders Audit Trail */}
          <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary mb-3 flex items-center justify-between">
              <span>Simulated Orders Audit Log ({orders.length})</span>
            </h3>

            {orders.length === 0 ? (
              <p className="text-xs text-alpha-text-secondary py-4 text-center">
                No simulated orders placed yet.
              </p>
            ) : (
              <div className="overflow-x-auto max-h-80 overflow-y-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="border-b border-alpha-border text-alpha-text-secondary">
                      <th className="text-left pb-2">Time</th>
                      <th className="text-left pb-2">Side</th>
                      <th className="text-right pb-2">Qty</th>
                      <th className="text-right pb-2">Fill Price</th>
                      <th className="text-center pb-2">Status</th>
                      <th className="text-right pb-2">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-alpha-border/40">
                    {orders.map((o) => (
                      <tr key={o.id} className="hover:bg-alpha-surface/50">
                        <td className="py-2 text-alpha-text-secondary">
                          {new Date(o.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </td>
                        <td className="py-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                            o.side === 'buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                          }`}>
                            {o.side} {o.order_type}
                          </span>
                        </td>
                        <td className="py-2 text-right text-alpha-text-secondary">{o.quantity.toFixed(4)}</td>
                        <td className="py-2 text-right text-alpha-text-primary">
                          {o.avg_fill_price ? `$${o.avg_fill_price.toFixed(2)}` : o.price ? `$${o.price.toFixed(2)}` : 'Market'}
                        </td>
                        <td className="py-2 text-center">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                            o.status === 'filled'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : o.status === 'open'
                              ? 'bg-blue-500/20 text-blue-400'
                              : o.status === 'rejected'
                              ? 'bg-rose-500/20 text-rose-400'
                              : 'bg-alpha-surface text-alpha-text-secondary'
                          }`}>
                            {o.status}
                          </span>
                        </td>
                        <td className="py-2 text-right">
                          {o.status === 'open' && (
                            <button
                              onClick={() => handleCancelOrder(o.id)}
                              className="text-rose-400 hover:text-rose-300 text-[11px] underline"
                            >
                              Cancel
                            </button>
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
      </div>

      {/* Resume Confirmation Modal */}
      {showResumeModal && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-alpha-card border border-alpha-border rounded-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 text-emerald-400">
              <ShieldCheck className="w-6 h-6" />
              <h3 className="text-base font-bold text-alpha-text-primary">Resume Trading Operations</h3>
            </div>
            <p className="text-xs text-alpha-text-secondary">
              Trading was halted by the Emergency Stop. To clear the halt, please enter the confirmation token{' '}
              <strong className="text-alpha-gold">CONFIRM_RESUME</strong>. Pre-trade risk controls and drawdown limits will remain actively enforced.
            </p>
            <form onSubmit={handleResume} className="space-y-4">
              <input
                type="text"
                value={resumeToken}
                onChange={(e) => setResumeToken(e.target.value)}
                placeholder="Type CONFIRM_RESUME"
                className="w-full bg-alpha-surface border border-alpha-border rounded-lg px-3 py-2 text-xs text-alpha-text-primary font-mono focus:outline-none focus:border-alpha-gold"
              />
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowResumeModal(false)}
                  className="px-3 py-1.5 text-xs text-alpha-text-secondary hover:text-alpha-text-primary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={resumeToken !== 'CONFIRM_RESUME'}
                  className="px-4 py-1.5 text-xs font-bold rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 transition-colors disabled:opacity-50"
                >
                  Confirm Resume
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
export default PortfolioPage;
