import { HealthResponse, ReadinessResponse, SystemInfo, SystemAuditLog } from '../types';

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
