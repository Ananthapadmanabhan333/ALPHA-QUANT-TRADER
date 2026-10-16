import {
  HealthResponse,
  ReadinessResponse,
  SystemInfo,
  SystemAuditLog,
  CandlesListResponse,
  MarketStatusResponse,
  StrategyInfo,
  StrategyExperiment,
  ExperimentListResponse,
  RunStrategyRequest,
  BacktestRun,
  BacktestListResponse,
  PerformanceAnalyticsResponse,
  BacktestCreateRequest,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message = errorBody?.error?.message || `HTTP Error ${response.status}: ${response.statusText}`;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`);
  return handleResponse<HealthResponse>(res);
}

export async function fetchReadiness(): Promise<ReadinessResponse> {
  const res = await fetch(`${API_BASE_URL}/ready`);
  return handleResponse<ReadinessResponse>(res);
}

export async function fetchSystemStatus(): Promise<SystemInfo> {
  const res = await fetch(`${API_BASE_URL}/api/v1/system/status`);
  return handleResponse<SystemInfo>(res);
}

export async function fetchSystemAuditLogs(limit: number = 20): Promise<SystemAuditLog[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/system/audit-logs?limit=${limit}`);
  return handleResponse<SystemAuditLog[]>(res);
}

export async function fetchCandles(
  symbol: string = 'BTCUSDT',
  interval: string = '1m',
  limit: number = 50,
  onlyClosed: boolean = true,
): Promise<CandlesListResponse> {
  const query = new URLSearchParams({
    symbol,
    interval,
    limit: limit.toString(),
    only_closed: onlyClosed.toString(),
  });
  const res = await fetch(`${API_BASE_URL}/api/v1/market/candles?${query.toString()}`);
  return handleResponse<CandlesListResponse>(res);
}

export async function fetchMarketStatus(
  symbol: string = 'BTCUSDT',
  interval: string = '1m',
): Promise<MarketStatusResponse> {
  const query = new URLSearchParams({ symbol, interval });
  const res = await fetch(`${API_BASE_URL}/api/v1/market/status?${query.toString()}`);
  return handleResponse<MarketStatusResponse>(res);
}

export async function fetchStrategies(): Promise<StrategyInfo[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/strategies`);
  return handleResponse<StrategyInfo[]>(res);
}

export async function runStrategy(payload: RunStrategyRequest): Promise<StrategyExperiment> {
  const res = await fetch(`${API_BASE_URL}/api/v1/strategies/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse<StrategyExperiment>(res);
}

export async function fetchExperiments(
  strategyId?: string,
  symbol?: string,
  limit: number = 50,
): Promise<ExperimentListResponse> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (strategyId) params.append('strategy_id', strategyId);
  if (symbol) params.append('symbol', symbol);
  const res = await fetch(`${API_BASE_URL}/api/v1/strategies/experiments?${params.toString()}`);
  return handleResponse<ExperimentListResponse>(res);
}

export async function fetchExperimentDetails(experimentId: string): Promise<StrategyExperiment> {
  const res = await fetch(`${API_BASE_URL}/api/v1/strategies/experiments/${experimentId}`);
  return handleResponse<StrategyExperiment>(res);
}

// ==========================================
// Phase 4: Backtesting Engine API
// ==========================================

export async function createBacktest(payload: BacktestCreateRequest): Promise<BacktestRun> {
  const res = await fetch(`${API_BASE_URL}/api/v1/backtests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse<BacktestRun>(res);
}

export async function fetchBacktestRuns(
  strategyId?: string,
  symbol?: string,
  limit: number = 50,
): Promise<BacktestListResponse> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (strategyId) params.append('strategy_id', strategyId);
  if (symbol) params.append('symbol', symbol);
  const res = await fetch(`${API_BASE_URL}/api/v1/backtests?${params.toString()}`);
  return handleResponse<BacktestListResponse>(res);
}

export async function fetchBacktestRun(runId: string): Promise<BacktestRun> {
  const res = await fetch(`${API_BASE_URL}/api/v1/backtests/${runId}`);
  return handleResponse<BacktestRun>(res);
}

export async function fetchPerformanceAnalytics(
  strategyId?: string,
): Promise<PerformanceAnalyticsResponse> {
  const params = new URLSearchParams();
  if (strategyId) params.append('strategy_id', strategyId);
  const res = await fetch(`${API_BASE_URL}/api/v1/analytics/performance?${params.toString()}`);
  return handleResponse<PerformanceAnalyticsResponse>(res);
}

