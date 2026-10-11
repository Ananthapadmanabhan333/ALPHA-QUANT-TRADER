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
