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
    <header className="h-16 border-b border-alpha-border bg-alpha-card/80 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-4">
        <button
          onClick={onToggleSidebar}
          aria-label="Toggle navigation sidebar"
          className="lg:hidden p-2 rounded-lg text-alpha-text-secondary hover:text-white hover:bg-alpha-cardHover transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3">
          <span className="hidden sm:inline-block px-2.5 py-0.5 rounded text-[11px] font-mono font-semibold tracking-wider bg-alpha-gold/15 text-alpha-gold border border-alpha-gold/30">
            PHASE 1 : FOUNDATION
          </span>
          <span className="hidden md:inline-block text-xs text-alpha-text-muted">
            Institutional Engine Core
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 sm:gap-6">
        {/* UTC Clock */}
        <div className="flex items-center gap-2 text-xs font-mono text-alpha-text-secondary bg-alpha-bg px-2.5 py-1 rounded border border-alpha-borderSubtle">
          <Clock className="w-3.5 h-3.5 text-alpha-gold" />
          <span>{time || '--:--:-- UTC'}</span>
        </div>

        {/* Live Backend Connection Indicator */}
        <div className="flex items-center gap-2">
          {health ? (
            <HealthBadge status={health.status} label={`Core: ${health.status}`} />
          ) : (
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-mono border border-alpha-border bg-alpha-bg text-alpha-text-muted">
              <Server className="w-3.5 h-3.5 animate-spin" />
              <span>Checking...</span>
            </div>
          )}

          <button
            onClick={checkStatus}
            disabled={isRefreshing}
            aria-label="Refresh status"
            title="Refresh backend status"
            className="p-1.5 rounded text-alpha-text-muted hover:text-alpha-gold transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-alpha-gold' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};
