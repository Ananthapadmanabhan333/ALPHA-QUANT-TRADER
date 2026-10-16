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
  PaperAccount,
  PaperOrder,
  PaperFill,
  RiskStatus,
  PaperOrderCreateRequest,
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

// ==========================================
// Phase 5: Paper Execution & Risk API
// ==========================================

export async function fetchPaperAccount(symbol: string = 'BTCUSDT'): Promise<PaperAccount> {
  const res = await fetch(`${API_BASE_URL}/api/v1/paper/account?symbol=${symbol}`);
  return handleResponse<PaperAccount>(res);
}

export async function fetchPaperOrders(
  status?: string,
  symbol?: string,
  limit: number = 50,
): Promise<PaperOrder[]> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (status) params.append('status', status);
  if (symbol) params.append('symbol', symbol);
  const res = await fetch(`${API_BASE_URL}/api/v1/paper/orders?${params.toString()}`);
  return handleResponse<PaperOrder[]>(res);
}

export async function fetchPaperOrderDetails(
  orderId: string,
): Promise<{ order: PaperOrder; fills: PaperFill[] }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/paper/orders/${orderId}`);
  return handleResponse<{ order: PaperOrder; fills: PaperFill[] }>(res);
}

export async function submitPaperOrder(payload: PaperOrderCreateRequest): Promise<PaperOrder> {
  const res = await fetch(`${API_BASE_URL}/api/v1/paper/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse<PaperOrder>(res);
}

export async function cancelPaperOrder(orderId: string): Promise<PaperOrder> {
  const res = await fetch(`${API_BASE_URL}/api/v1/paper/orders/${orderId}`, {
    method: 'DELETE',
  });
  return handleResponse<PaperOrder>(res);
}

export async function fetchRiskStatus(symbol: string = 'BTCUSDT'): Promise<RiskStatus> {
  const res = await fetch(`${API_BASE_URL}/api/v1/paper/risk/status?symbol=${symbol}`);
  return handleResponse<RiskStatus>(res);
}

export async function triggerEmergencyStop(reason: string): Promise<RiskStatus> {
  const res = await fetch(`${API_BASE_URL}/api/v1/paper/risk/emergency-stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  return handleResponse<RiskStatus>(res);
}

export async function resumeEmergencyStop(
  confirmation: string = 'CONFIRM_RESUME',
  resetConsecutiveLosses: boolean = false,
): Promise<RiskStatus> {
  const res = await fetch(`${API_BASE_URL}/api/v1/paper/risk/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      confirmation,
      reset_consecutive_losses: resetConsecutiveLosses,
    }),
  });
  return handleResponse<RiskStatus>(res);
}


