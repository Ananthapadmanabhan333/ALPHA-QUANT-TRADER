import React from 'react';
import { PieChart, Briefcase } from 'lucide-react';
import { EmptyState } from '../components/common/EmptyState';

export const PortfolioPage: React.FC = () => {
  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-alpha-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-alpha-text-primary flex items-center gap-3">
            <PieChart className="w-6 h-6 text-alpha-gold" />
            <span>Portfolio Engine</span>
          </h1>
          <p className="text-sm text-alpha-text-secondary mt-1">
            Institutional Asset Allocation, Risk Parity, and Position Monitoring
          </p>
        </div>
      </div>

      <div className="py-8">
        <EmptyState
          icon={<Briefcase className="w-7 h-7" />}
          title="No Portfolios Configured"
          description="Portfolio tracking, balance attribution, and real-time PnL computation will be activated in Phase 2. ALPHA Quant never displays fabricated balances or fake profit metrics."
          phaseRequired={2}
          actionText="Inspect System Architecture"
          actionHref="/system-health"
        />
      </div>
    </div>
  );
};
