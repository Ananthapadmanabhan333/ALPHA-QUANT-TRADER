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
  PaperFill,
  PaperOrderCreateRequest,
  RiskStatus,
} from '../types';
import {
  fetchPaperAccount,
  fetchPaperOrders,
  fetchFills,
  submitPaperOrder,
  cancelPaperOrder,
  fetchRiskStatus,
  triggerEmergencyStop,
  resumeEmergencyStop,
  fetchMarketStatus,
  fetchCandles,
  resetPaperAccount,
} from '../services/api';

export const PortfolioPage: React.FC = () => {
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [fills, setFills] = useState<PaperFill[]>([]);
  const [activeLedgerTab, setActiveLedgerTab] = useState<'orders' | 'fills'>('orders');
  const [risk, setRisk] = useState<RiskStatus | null>(null);
  const [livePrice, setLivePrice] = useState<number>(81300);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Order form state
  const [orderSide, setOrderSide] = useState<'buy' | 'sell'>('buy');
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [symbol] = useState<string>('BTCUSDT');
  const [quantity, setQuantity] = useState<number>(0.01);
  const [price, setPrice] = useState<number>(81300);
  const [priceInitialized, setPriceInitialized] = useState<boolean>(false);

  // Resume modal state
  const [showResumeModal, setShowResumeModal] = useState<boolean>(false);
  const [resumeToken, setResumeToken] = useState<string>('');

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [acc, orderList, fillsList, riskStat, mktStat, candleRes] = await Promise.all([
        fetchPaperAccount().catch(() => null),
        fetchPaperOrders().catch(() => []),
        fetchFills().catch(() => ({ total: 0, limit: 50, offset: 0, items: [] })),
        fetchRiskStatus().catch(() => null),
        fetchMarketStatus('BTCUSDT', '1m').catch(() => null),
        fetchCandles('BTCUSDT', '1m', 1, false).catch(() => null),
      ]);
      setAccount(acc);
      setOrders(orderList);
      setFills(fillsList.items || []);
      setRisk(riskStat);

      const detectedPrice =
        mktStat?.latest_close_price ||
        candleRes?.candles?.[candleRes.candles.length - 1]?.close ||
        acc?.positions?.[0]?.current_price;

      if (detectedPrice && detectedPrice > 0) {
        setLivePrice(detectedPrice);
        if (!priceInitialized) {
          setPrice(Math.round(detectedPrice));
          setPriceInitialized(true);
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load paper broker data.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = window.setInterval(loadData, 5000);
    return () => clearInterval(interval);
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
      setSuccessMsg(`Simulated order executed: ${result.side.toUpperCase()} ${result.quantity} ${result.symbol} [${result.status.toUpperCase()}]`);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Order submission failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFlattenPosition = async (posSymbol: string, posQuantity: number) => {
    if (posQuantity <= 0) return;
    setIsSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const result = await submitPaperOrder({
        symbol: posSymbol,
        side: 'sell',
        order_type: 'market',
        quantity: posQuantity,
      });
      setSuccessMsg(`Flattened position: SOLD ${result.quantity} ${result.symbol} @ Market [${result.status.toUpperCase()}]`);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to flatten position.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetCapital = async (targetCapital: number) => {
    if (!window.confirm(`Reset simulated account to $${targetCapital.toLocaleString()} USDT and flatten open paper positions?`)) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await resetPaperAccount(targetCapital, true);
      setSuccessMsg(`Virtual account capital reset to $${targetCapital.toLocaleString()} USDT.`);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reset paper account.');
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
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-alpha-text-primary flex items-center gap-3">
            <Briefcase className="w-6 h-6 text-alpha-gold" />
            <span>Paper Execution & Central Risk Control</span>
          </h1>
          <p className="text-sm text-alpha-text-secondary mt-1">
            Simulated Spot Inventory, Pre-Trade Risk Gate, Ledger Invariants & Automated Emergency Halt
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 bg-alpha-surface border border-alpha-border rounded-lg p-1 mr-1">
            <span className="text-[10px] font-mono text-alpha-text-muted px-2 uppercase">Set Capital:</span>
            {[10000, 25000, 50000, 100000].map((cap) => (
              <button
                key={cap}
                type="button"
                disabled={isSubmitting}
                onClick={() => handleResetCapital(cap)}
                className="px-2 py-1 text-[11px] font-mono font-semibold rounded bg-alpha-card hover:bg-alpha-gold/20 text-alpha-text-secondary hover:text-alpha-gold border border-alpha-borderSubtle transition-colors"
                title={`Reset virtual equity to $${cap.toLocaleString()} USDT`}
              >
                ${cap / 1000}k
              </button>
            ))}
          </div>

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
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-alpha-card border border-alpha-border rounded-xl p-3.5 sm:p-4">
          <div className="flex items-center justify-between">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary truncate">Virtual Cash</span>
            <DollarSign className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-alpha-gold shrink-0" />
          </div>
          <p className="text-lg sm:text-2xl font-mono font-bold text-alpha-text-primary mt-1.5 sm:mt-2 truncate">
            ${(account?.virtual_balance ?? 10000).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-[10px] sm:text-[11px] text-alpha-text-secondary mt-1">USDT Available</p>
        </div>

        <div className="bg-alpha-card border border-alpha-border rounded-xl p-3.5 sm:p-4">
          <div className="flex items-center justify-between">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary truncate">Total Equity</span>
            <Layers className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-alpha-gold shrink-0" />
          </div>
          <p className="text-lg sm:text-2xl font-mono font-bold text-alpha-text-primary mt-1.5 sm:mt-2 truncate">
            ${(account?.total_equity ?? 10000).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-[10px] sm:text-[11px] text-alpha-text-secondary mt-1">Cash + Inventory</p>
        </div>

        <div className="bg-alpha-card border border-alpha-border rounded-xl p-3.5 sm:p-4">
          <div className="flex items-center justify-between">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary truncate">Realized P&L</span>
            <TrendingUp className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-400 shrink-0" />
          </div>
          <p className={`text-lg sm:text-2xl font-mono font-bold mt-1.5 sm:mt-2 truncate ${(account?.realized_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            ${(account?.realized_pnl ?? 0) >= 0 ? '+' : ''}{(account?.realized_pnl ?? 0).toFixed(2)}
          </p>
          <p className="text-[10px] sm:text-[11px] text-alpha-text-secondary mt-1">Post Fees & Slip</p>
        </div>

        <div className="bg-alpha-card border border-alpha-border rounded-xl p-3.5 sm:p-4">
          <div className="flex items-center justify-between">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary truncate">Unrealized P&L</span>
            <TrendingDown className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-alpha-gold shrink-0" />
          </div>
          <p className={`text-lg sm:text-2xl font-mono font-bold mt-1.5 sm:mt-2 truncate ${(account?.unrealized_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            ${(account?.unrealized_pnl ?? 0) >= 0 ? '+' : ''}{(account?.unrealized_pnl ?? 0).toFixed(2)}
          </p>
          <p className="text-[10px] sm:text-[11px] text-alpha-text-secondary mt-1">Mark-to-Market</p>
        </div>
      </div>

      {/* Central Risk Gate Telemetry Bar */}
      {risk && (
        <div className="bg-alpha-card border border-alpha-border rounded-xl p-4 sm:p-5 shadow-sm space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-alpha-border pb-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-alpha-text-secondary flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-alpha-gold shrink-0" />
              <span>Central Pre-Trade Risk Gate Telemetry</span>
            </h3>
            <div className="flex flex-wrap items-center gap-2">
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

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 text-xs font-mono">
            <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
              <span className="text-alpha-text-secondary text-[11px]">Drawdown</span>
              <p className={`text-sm sm:text-base font-bold mt-1 ${risk.current_drawdown_pct >= risk.max_drawdown_limit_pct ? 'text-rose-400' : 'text-alpha-text-primary'}`}>
                {risk.current_drawdown_pct.toFixed(2)}%
              </p>
              <span className="text-[10px] text-alpha-text-secondary">Limit: {risk.max_drawdown_limit_pct.toFixed(1)}%</span>
            </div>

            <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
              <span className="text-alpha-text-secondary text-[11px]">Daily P&L</span>
              <p className="text-sm sm:text-base font-bold text-alpha-text-primary mt-1">
                ${risk.current_daily_pnl.toFixed(2)}
              </p>
              <span className="text-[10px] text-alpha-text-secondary">Limit: {risk.daily_loss_limit_pct.toFixed(1)}%</span>
            </div>

            <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
              <span className="text-alpha-text-secondary text-[11px]">Loss Streak</span>
              <p className={`text-sm sm:text-base font-bold mt-1 ${risk.consecutive_losses >= risk.consecutive_loss_limit ? 'text-rose-400' : 'text-alpha-text-primary'}`}>
                {risk.consecutive_losses} trades
              </p>
              <span className="text-[10px] text-alpha-text-secondary">Limit: {risk.consecutive_loss_limit} max</span>
            </div>

            <div className="bg-alpha-surface border border-alpha-border rounded-lg p-3">
              <span className="text-alpha-text-secondary text-[11px]">Max Limits</span>
              <p className="text-sm sm:text-base font-bold text-alpha-gold mt-1 truncate">
                {risk.max_position_pct.toFixed(0)}% / ${risk.max_order_notional.toLocaleString()}
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
          <div className="bg-alpha-card border border-alpha-border rounded-xl p-4 sm:p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <h2 className="text-sm sm:text-base font-semibold text-alpha-text-primary flex items-center gap-2">
                <Play className="w-4 h-4 text-alpha-gold shrink-0" />
                <span>Submit Simulated Order</span>
              </h2>
              <span className="px-2 py-0.5 text-[11px] font-mono font-bold rounded bg-alpha-gold/15 text-alpha-gold border border-alpha-gold/30">
                BTC: ${livePrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

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
                <div className="flex flex-wrap items-center justify-between gap-1.5 mb-1.5">
                  <label className="block text-xs font-semibold text-alpha-text-secondary">
                    Quantity ({symbol.replace('USDT', '')})
                  </label>
                  <div className="flex flex-wrap items-center gap-1">
                    {[0.002, 0.005, 0.01].map((q) => (
                      <button
                        key={q}
                        type="button"
                        onClick={() => setQuantity(q)}
                        className="px-2 py-0.5 text-[10px] font-mono rounded bg-alpha-surface border border-alpha-border text-alpha-text-secondary hover:text-alpha-gold hover:border-alpha-gold/50 transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                    {orderSide === 'buy' ? (
                      <button
                        type="button"
                        onClick={() => {
                          const eq = account?.total_equity ?? 10000;
                          const maxSafeNotional = eq * 0.095;
                          const refP = orderType === 'limit' ? price : livePrice;
                          if (refP > 0) setQuantity(Number((maxSafeNotional / refP).toFixed(4)));
                        }}
                        className="px-2 py-0.5 text-[10px] font-mono rounded bg-alpha-gold/10 border border-alpha-gold/40 text-alpha-gold hover:bg-alpha-gold/20 transition-colors"
                        title="Size to 9.5% of equity (within 10% risk gate concentration limit)"
                      >
                        Max Safe
                      </button>
                    ) : (
                      account?.positions && account.positions.length > 0 && (
                        <button
                          type="button"
                          onClick={() => setQuantity(Number((account.positions[0]?.quantity ?? 0).toFixed(4)))}
                          className="px-2 py-0.5 text-[10px] font-mono rounded bg-rose-500/15 border border-rose-500/40 text-rose-300 hover:bg-rose-500/25 transition-colors"
                        >
                          100% Pos
                        </button>
                      )
                    )}
                  </div>
                </div>
                <input
                  type="number"
                  step="0.0001"
                  min="0.0001"
                  value={quantity}
                  onChange={(e) => setQuantity(Number(e.target.value))}
                  className="w-full bg-alpha-surface border border-alpha-border rounded-lg px-3 py-2 text-xs text-alpha-text-primary font-mono focus:outline-none focus:border-alpha-gold"
                />
              </div>

              {orderType === 'limit' && (
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-1.5 mb-1.5">
                    <label className="block text-xs font-semibold text-alpha-text-secondary">
                      Limit Price ($ USD)
                    </label>
                    <div className="flex flex-wrap items-center gap-1">
                      {[
                        { label: '-0.5%', mult: 0.995 },
                        { label: '-0.1%', mult: 0.999 },
                        { label: 'Mkt', mult: 1.0 },
                        { label: '+0.1%', mult: 1.001 },
                        { label: '+0.5%', mult: 1.005 },
                      ].map((btn) => (
                        <button
                          key={btn.label}
                          type="button"
                          onClick={() => setPrice(Math.round(livePrice * btn.mult))}
                          className="px-2 py-0.5 text-[10px] font-mono rounded bg-alpha-surface border border-alpha-border text-alpha-text-secondary hover:text-alpha-gold hover:border-alpha-gold/50 transition-colors"
                        >
                          {btn.label}
                        </button>
                      ))}
                    </div>
                  </div>
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

              {(() => {
                const refP = orderType === 'limit' ? price : livePrice;
                const estNotional = quantity * refP;
                const eq = account?.total_equity ?? 10000;
                const pctOfEq = eq > 0 ? (estNotional / eq) * 100 : 0;
                const isOverCap = orderSide === 'buy' && pctOfEq > (risk?.max_position_pct ?? 10);
                return (
                  <div className="p-3 bg-alpha-surface border border-alpha-border rounded-lg text-[11px] text-alpha-text-secondary space-y-1">
                    <div className="flex justify-between">
                      <span>Estimated Notional:</span>
                      <span className={`font-mono font-semibold ${isOverCap ? 'text-rose-400' : 'text-alpha-text-primary'}`}>
                        ${estNotional.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD ({pctOfEq.toFixed(1)}% Eq)
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
                      <span className={`font-mono ${isOverCap ? 'text-rose-400 font-bold' : 'text-alpha-gold'}`}>
                        {(risk?.max_position_pct ?? 10).toFixed(1)}% of virtual equity (${((eq * (risk?.max_position_pct ?? 10)) / 100).toFixed(0)} max)
                      </span>
                    </div>
                  </div>
                );
              })()}

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
                      <th className="text-right pb-2">Action</th>
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
                        <td className="py-2.5 text-right">
                          <button
                            type="button"
                            disabled={isSubmitting || p.quantity <= 0}
                            onClick={() => handleFlattenPosition(p.symbol, p.quantity)}
                            className="px-2 py-0.5 text-[10px] font-bold rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30 transition-colors disabled:opacity-50"
                          >
                            Flatten
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Orders & Fills Ledger Card with Tabs */}
          <div className="bg-alpha-card border border-alpha-border rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-alpha-border pb-3">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveLedgerTab('orders')}
                  className={`px-3 py-1 text-xs font-mono rounded font-semibold transition-colors ${
                    activeLedgerTab === 'orders'
                      ? 'bg-alpha-gold text-black'
                      : 'bg-alpha-surface text-alpha-text-secondary hover:text-white'
                  }`}
                >
                  Orders Log ({orders.length})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveLedgerTab('fills')}
                  className={`px-3 py-1 text-xs font-mono rounded font-semibold transition-colors ${
                    activeLedgerTab === 'fills'
                      ? 'bg-alpha-gold text-black'
                      : 'bg-alpha-surface text-alpha-text-secondary hover:text-white'
                  }`}
                >
                  Execution Fills Ledger ({fills.length})
                </button>
              </div>

              <span className="text-[10px] font-mono text-alpha-text-muted">
                {activeLedgerTab === 'orders' ? 'Simulated Lifecycle' : 'Audited Fills & Drag'}
              </span>
            </div>

            {activeLedgerTab === 'orders' ? (
              orders.length === 0 ? (
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
              )
            ) : (
              fills.length === 0 ? (
                <p className="text-xs text-alpha-text-secondary py-4 text-center">
                  No simulated execution fills recorded yet.
                </p>
              ) : (
                <div className="overflow-x-auto max-h-80 overflow-y-auto">
                  <table className="w-full text-xs font-mono">
                    <thead>
                      <tr className="border-b border-alpha-border text-alpha-text-secondary">
                        <th className="text-left pb-2">Time (UTC)</th>
                        <th className="text-left pb-2">Side</th>
                        <th className="text-right pb-2">Fill Price</th>
                        <th className="text-right pb-2">Qty</th>
                        <th className="text-right pb-2">Notional</th>
                        <th className="text-right pb-2">Fee</th>
                        <th className="text-right pb-2">Slippage</th>
                        <th className="text-right pb-2">Realized P&L</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-alpha-border/40">
                      {fills.map((f) => (
                        <tr key={f.id} className="hover:bg-alpha-surface/50">
                          <td className="py-2 text-alpha-text-secondary">
                            {new Date(f.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                          </td>
                          <td className="py-2">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                              f.side === 'buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                            }`}>
                              {f.side}
                            </span>
                          </td>
                          <td className="py-2 text-right text-alpha-text-primary">
                            ${f.fill_price.toFixed(2)}
                          </td>
                          <td className="py-2 text-right text-alpha-text-secondary">{f.quantity.toFixed(4)}</td>
                          <td className="py-2 text-right text-alpha-text-secondary">${f.gross_notional.toFixed(2)}</td>
                          <td className="py-2 text-right text-alpha-gold">${f.fee.toFixed(2)}</td>
                          <td className="py-2 text-right text-rose-300">${f.slippage_cost.toFixed(2)}</td>
                          <td className={`py-2 text-right font-bold ${
                            f.realized_pnl > 0 ? 'text-emerald-400' : f.realized_pnl < 0 ? 'text-rose-400' : 'text-alpha-text-secondary'
                          }`}>
                            ${f.realized_pnl.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
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

export const PaperTradingPage = PortfolioPage;
export default PortfolioPage;
