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
