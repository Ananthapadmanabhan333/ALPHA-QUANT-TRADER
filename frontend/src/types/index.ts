export type HealthStatus = 'healthy' | 'unhealthy' | 'degraded' | 'unknown';

export interface DatabaseHealth {
  status: 'healthy' | 'unhealthy' | string;
  connected: boolean;
  latency_ms?: number;
  dialect?: string;
  error?: string;
}

export interface HealthResponse {
  status: HealthStatus;
  version: string;
  environment: string;
  timestamp: string;
}

export interface ReadinessResponse {
  status: 'ready' | 'not_ready' | string;
  ready: boolean;
  timestamp: string;
  components: {
    database: DatabaseHealth;
    [key: string]: unknown;
  };
}

export interface SystemInfo {
  project_name: string;
  version: string;
  environment: string;
  debug: boolean;
  timestamp: string;
  uptime_seconds: number;
  database: DatabaseHealth;
}

export interface SystemAuditLog {
  id: string;
  component: string;
  event_type: string;
  status: string;
  message: string;
  payload?: Record<string, unknown> | null;
  created_at: string;
}

export interface NavItem {
  name: string;
  path: string;
  iconName: string;
  phase: number;
  badge?: string;
}

export interface MarketCandle {
  symbol: string;
  interval: string;
  open_time: string;
  close_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  quote_volume: number;
  trades_count: number;
  is_closed: boolean;
  source: string;
  exchange_event_time?: string | null;
  ingested_at: string;
}

export interface CandlesListResponse {
  symbol: string;
  interval: string;
  count: number;
  only_closed: boolean;
  start_time?: string | null;
  end_time?: string | null;
  candles: MarketCandle[];
}

export interface MarketStatusResponse {
  symbol: string;
  interval: string;
  feed_state: 'DISCONNECTED' | 'CONNECTING' | 'STREAMING' | 'BACKFILLING' | 'STALE' | 'ERROR' | string;
  connected: boolean;
  is_streaming: boolean;
  last_exchange_time?: string | null;
  last_ingested_at?: string | null;
  latest_close_price?: number | null;
  messages_received: number;
  candles_saved: number;
  gap_count: number;
  error_count: number;
  reconnect_count: number;
  is_stale: boolean;
  rate_limit_remaining: number;
  timestamp: string;
}

export type SignalSide = 'buy' | 'sell' | 'hold';

export interface StrategyInfo {
  strategy_id: string;
  name: string;
  version: string;
  description: string;
  candidate_parameters: Record<string, unknown>;
  features_used: string[];
}

export interface StrategySignal {
  strategy_id: string;
  strategy_version: string;
  decision_timestamp: string;
  symbol: string;
  side: SignalSide | string;
  signal_score: number;
  reference_price: number;
  reason: string;
  relevant_features: Record<string, number | null>;
  config_id: string;
}

export interface StrategyExperiment {
  id: string;
  strategy_id: string;
  strategy_version: string;
  config_id: string;
  symbol: string;
  interval: string;
  time_range_start: string;
  time_range_end: string;
  candle_count: number;
  dataset_fingerprint: string;
  parameters: Record<string, unknown>;
  total_signals: number;
  buy_signals: number;
  sell_signals: number;
  hold_signals: number;
  created_at: string;
  signals?: StrategySignal[];
}

export interface ExperimentListResponse {
  count: number;
  experiments: StrategyExperiment[];
}

export interface RunStrategyRequest {
  strategy_id: string;
  symbol?: string;
  interval?: string;
  parameters?: Record<string, unknown>;
  limit?: number;
}

// ==========================================
// Phase 4: Backtesting Engine Types
// ==========================================

export interface EquitySnapshot {
  timestamp: string;
  cash: number;
  positions_value: number;
  total_equity: number;
  gross_pnl: number;
  net_pnl: number;
  cumulative_fees: number;
  cumulative_slippage: number;
  drawdown_pct: number;
  in_position: boolean;
}

export interface BacktestTrade {
  trade_id: string;
  order_id: string;
  timestamp: string;
  symbol: string;
  side: string;
  fill_price: number;
  quantity: number;
  gross_notional: number;
  fee: number;
  slippage_cost: number;
  realized_gross_pnl: number;
  realized_net_pnl: number;
}

export interface StressScenarioResult {
  scenario: string;
  net_return_pct: number;
  max_drawdown_pct: number;
  total_fees: number;
  total_slippage: number;
}

export interface RegimePerformance {
  candles_count: number;
  time_pct: number;
  gross_return_pct: number;
}

export interface BacktestRun {
  id: string;
  strategy_id: string;
  strategy_version: string;
  config_id: string;
  symbol: string;
  interval: string;
  time_range_start: string;
  time_range_end: string;
  candle_count: number;
  dataset_fingerprint: string;
  parameters: Record<string, unknown>;
  cost_assumptions: Record<string, unknown>;
  status: string;
  metrics: Record<string, unknown>;
  total_trades: number;
  net_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  profit_factor?: number | null;
  win_rate_pct: number;
  created_at: string;
  completed_at?: string | null;
  equity_curve?: EquitySnapshot[];
  trades?: BacktestTrade[];
  regime_performance?: Record<string, RegimePerformance>;
  stress_test_results?: Record<string, StressScenarioResult>;
}

export interface BacktestListResponse {
  count: number;
  backtests: BacktestRun[];
}

export interface PerformanceAnalyticsResponse {
  strategy_id?: string | null;
  total_backtests: number;
  avg_net_return_pct: number;
  avg_sharpe_ratio: number;
  avg_max_drawdown_pct: number;
  best_net_return_pct: number;
  worst_net_return_pct: number;
  runs: Array<Record<string, unknown>>;
}

export interface BacktestCreateRequest {
  strategy_id: string;
  symbol?: string;
  interval?: string;
  initial_cash?: number;
  start_time?: string;
  end_time?: string;
  parameters?: Record<string, unknown>;
  cost_assumptions?: {
    maker_fee_bps?: number;
    taker_fee_bps?: number;
    slippage_bps?: number;
    max_volume_pct?: number;
  };
  stress_scenarios?: boolean;
}

// ==========================================
// Phase 5: Paper Execution & Risk Types
// ==========================================

export interface PaperOrder {
  id: string;
  client_order_id: string;
  account_id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  price?: number | null;
  filled_quantity: number;
  avg_fill_price?: number | null;
  status: string;
  fee: number;
  slippage_cost: number;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaperFill {
  id: string;
  order_id: string;
  symbol: string;
  side: string;
  fill_price: number;
  quantity: number;
  gross_notional: number;
  fee: number;
  slippage_cost: number;
  realized_pnl: number;
  created_at: string;
}

export interface PaperPosition {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  cost_basis: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
}

export interface PaperAccount {
  account_id: string;
  name: string;
  virtual_balance: number;
  currency: string;
  total_positions_value: number;
  total_equity: number;
  unrealized_pnl: number;
  realized_pnl: number;
  positions: PaperPosition[];
  is_active: boolean;
  created_at: string;
}

export interface RiskStatus {
  emergency_stop: boolean;
  kill_switch_reason?: string | null;
  max_order_notional: number;
  max_position_pct: number;
  max_portfolio_exposure_pct: number;
  daily_loss_limit_pct: number;
  max_drawdown_limit_pct: number;
  consecutive_loss_limit: number;
  starting_daily_equity: number;
  current_daily_pnl: number;
  peak_equity: number;
  current_drawdown_pct: number;
  consecutive_losses: number;
  last_breach_reason?: string | null;
  feed_status: string;
  last_feed_time?: string | null;
  is_trading_allowed: boolean;
}

export interface PaperOrderCreateRequest {
  symbol?: string;
  side: 'buy' | 'sell';
  order_type?: 'market' | 'limit';
  quantity: number;
  price?: number;
  client_order_id?: string;
  current_market_price?: number;
}

// ==========================================
// Phase 6 & 7: Orchestration, Lifecycle & Events
// ==========================================

export interface PaginatedResponse<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export interface PaperTradingStartRequest {
  strategy_id: string;
  symbol?: string;
  interval?: string;
  poll_interval_seconds?: number;
  order_size_pct?: number;
  parameters?: Record<string, unknown>;
}

export interface PaperTradingStartResponse {
  status: string;
  strategy_id: string;
  symbol: string;
  interval: string;
  poll_interval_seconds: number;
  started_at: string;
  message: string;
}

export interface PaperTradingStopResponse {
  status: string;
  stopped_at: string;
  cycles_completed: number;
  orders_submitted: number;
  signals_evaluated: number;
  message: string;
}

export interface PaperTradingStatus {
  is_running: boolean;
  strategy_id?: string | null;
  symbol?: string | null;
  interval?: string | null;
  poll_interval_seconds?: number | null;
  started_at?: string | null;
  cycles_completed: number;
  signals_evaluated: number;
  orders_submitted: number;
  last_cycle_at?: string | null;
  last_error?: string | null;
  lock_acquired: boolean;
  task_active: boolean;
}

export interface RiskResetRequest {
  confirmation_code: string;
  reset_emergency_stop?: boolean;
  reset_consecutive_losses?: boolean;
  reset_daily_loss?: boolean;
  reason: string;
}

export interface RiskResetResponse {
  success: boolean;
  message: string;
  timestamp: string;
  risk_state: Record<string, unknown>;
}

export interface SystemEvent {
  id: string;
  account_id: string;
  event_type: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL' | string;
  reason: string;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface AsyncTaskResponse {
  task_id: string;
  task_type: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  result?: Record<string, unknown> | null;
}

export interface LiveIndicators {
  close: number;
  sma_20?: number | null;
  sma_100?: number | null;
  ema_20?: number | null;
  trend_spread_bps?: number | null;
  zscore_60?: number | null;
  atr_14?: number | null;
  atr_bps?: number | null;
  volatility_20?: number | null;
  momentum_5?: number | null;
  momentum_15?: number | null;
  momentum_60?: number | null;
  volume_ratio_20?: number | null;
}

export interface LiveTradeSetup {
  strategy_id: string;
  strategy_name: string;
  side: 'buy' | 'sell' | 'hold' | string;
  signal_score: number;
  reason: string;
  entry_price: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  risk_reward_ratio: number;
  recommended_qty: number;
  recommended_notional_usd: number;
  relevant_features?: Record<string, unknown>;
}

export interface LiveScannerResponse {
  symbol: string;
  interval: string;
  timestamp: string;
  regime: string;
  consensus_side: string;
  consensus_score: number;
  indicators: LiveIndicators;
  setups: LiveTradeSetup[];
}




