import React, { useEffect, useState } from 'react';
import { Clock, Server, Menu, RefreshCw } from 'lucide-react';
import { fetchHealth } from '../../services/api';
import { HealthResponse } from '../../types';
import { HealthBadge } from '../common/HealthBadge';

interface AppHeaderProps {
  onToggleSidebar: () => void;
}

export const AppHeader: React.FC<AppHeaderProps> = ({ onToggleSidebar }) => {
  const [time, setTime] = useState<string>('');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(now.toISOString().slice(11, 19) + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const checkStatus = async () => {
    setIsRefreshing(true);
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch {
      setHealth({
        status: 'unhealthy',
        version: '1.0.0',
        environment: 'development',
        timestamp: new Date().toISOString(),
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-14 sm:h-16 border-b border-alpha-border bg-alpha-card/85 backdrop-blur-md px-3 sm:px-6 flex items-center justify-between gap-2 sticky top-0 z-30 shrink-0">
      <div className="flex items-center gap-2 sm:gap-4 min-w-0">
        <button
          onClick={onToggleSidebar}
          aria-label="Toggle navigation sidebar"
          className="lg:hidden p-2 -ml-1 rounded-lg text-alpha-text-secondary hover:text-white hover:bg-alpha-cardHover transition-colors shrink-0"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <span className="inline-block px-2 sm:px-2.5 py-0.5 rounded text-[10px] sm:text-[11px] font-mono font-semibold tracking-wider bg-alpha-gold/15 text-alpha-gold border border-alpha-gold/30 truncate">
            ALPHA QUANT
          </span>
          <span className="hidden md:inline-block text-xs font-mono text-alpha-text-muted truncate">
            Institutional Engine Core
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1.5 sm:gap-4 shrink-0">
        {/* UTC Clock */}
        <div className="flex items-center gap-1.5 text-[10px] sm:text-xs font-mono text-alpha-text-secondary bg-alpha-bg px-2 sm:px-2.5 py-1 rounded border border-alpha-borderSubtle">
          <Clock className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-alpha-gold shrink-0" />
          <span className="whitespace-nowrap">{time || '--:--:-- UTC'}</span>
        </div>

        {/* Live Backend Connection Indicator */}
        <div className="flex items-center gap-1 sm:gap-2">
          {health ? (
            <HealthBadge status={health.status} label={health.status === 'healthy' ? 'LIVE' : health.status} />
          ) : (
            <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] sm:text-xs font-mono border border-alpha-border bg-alpha-bg text-alpha-text-muted">
              <Server className="w-3 h-3 animate-spin" />
              <span className="hidden xs:inline">Sync...</span>
            </div>
          )}

          <button
            onClick={checkStatus}
            disabled={isRefreshing}
            aria-label="Refresh status"
            title="Refresh backend status"
            className="p-1.5 rounded text-alpha-text-muted hover:text-alpha-gold transition-colors shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-alpha-gold' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};
