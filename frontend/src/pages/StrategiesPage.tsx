import React from 'react';
import { LineChart, Cpu } from 'lucide-react';
import { EmptyState } from '../components/common/EmptyState';

export const StrategiesPage: React.FC = () => {
  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-alpha-text-primary flex items-center gap-3">
            <LineChart className="w-6 h-6 text-alpha-gold" />
            <span>Quant Strategies</span>
          </h1>
          <p className="text-sm text-alpha-text-secondary mt-1">
            Factor Models, Statistical Arbitrage, and Autonomous Alpha Engines
          </p>
        </div>
      </div>

      <div className="py-8">
        <EmptyState
          icon={<Cpu className="w-7 h-7" />}
          title="No Active Quantitative Strategies"
          description="Algorithm runners, factor scoring, and backtesting pipelines will be mounted during Phase 3. No synthetic trade executions are simulated."
          phaseRequired={3}
          actionText="Inspect System Architecture"
          actionHref="/system-health"
        />
      </div>
    </div>
  );
};
