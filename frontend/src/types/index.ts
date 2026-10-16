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

