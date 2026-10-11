import React from 'react';
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { HealthStatus } from '../../types';

interface HealthBadgeProps {
  status: HealthStatus | string;
  latencyMs?: number;
  label?: string;
  showIcon?: boolean;
}

export const HealthBadge: React.FC<HealthBadgeProps> = ({
  status,
  latencyMs,
  label,
  showIcon = true,
}) => {
  const isHealthy = status === 'healthy' || status === 'ready' || status === 'operational';
  const isDegraded = status === 'degraded';

  const badgeConfig = isHealthy
    ? {
        bg: 'bg-emerald-950/40',
        border: 'border-emerald-800/50',
        text: 'text-emerald-400',
        dot: 'bg-emerald-400',
        icon: CheckCircle,
      }
    : isDegraded
    ? {
        bg: 'bg-amber-950/40',
        border: 'border-amber-800/50',
        text: 'text-amber-400',
        dot: 'bg-amber-400',
        icon: AlertTriangle,
      }
    : {
        bg: 'bg-rose-950/40',
        border: 'border-rose-800/50',
        text: 'text-rose-400',
        dot: 'bg-rose-400',
        icon: XCircle,
      };

  const IconComponent = badgeConfig.icon;

  return (
    <div
      className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-mono border ${badgeConfig.bg} ${badgeConfig.border} ${badgeConfig.text}`}
    >
      <span className={`w-2 h-2 rounded-full ${badgeConfig.dot} animate-pulse`} />
      {showIcon && <IconComponent className="w-3.5 h-3.5" />}
      <span className="capitalize font-medium">{label || status}</span>
      {typeof latencyMs === 'number' && (
        <span className="text-alpha-text-muted border-l border-alpha-border pl-2 text-[11px]">
          {latencyMs}ms
        </span>
      )}
    </div>
  );
};
