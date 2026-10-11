import React from 'react';
import { ShieldAlert, Database, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

interface EmptyStateProps {
  title: string;
  description: string;
  phaseRequired?: number;
  actionText?: string;
  actionHref?: string;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  phaseRequired,
  actionText,
  actionHref,
  icon,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-xl border border-alpha-border bg-alpha-card/50 backdrop-blur-sm">
      <div className="w-14 h-14 rounded-full bg-alpha-gold-dim border border-alpha-gold/30 flex items-center justify-center text-alpha-gold mb-4">
        {icon || <ShieldAlert className="w-7 h-7" />}
      </div>

      <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium text-alpha-gold bg-alpha-gold/10 border border-alpha-gold/20 mb-3">
        <span>{phaseRequired ? `Available in Phase ${phaseRequired}` : 'Phase 1 Foundation'}</span>
      </div>

      <h3 className="text-lg font-semibold text-alpha-text-primary mb-2">
        {title}
      </h3>

      <p className="text-sm text-alpha-text-secondary max-w-md mb-6 leading-relaxed">
        {description}
      </p>

      {actionText && actionHref && (
        <Link
          to={actionHref}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium text-black bg-alpha-gold hover:bg-alpha-gold-light rounded-lg transition-colors shadow-sm font-sans"
        >
          <span>{actionText}</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      )}

      <div className="mt-8 pt-6 border-t border-alpha-borderSubtle w-full max-w-xs flex items-center justify-center gap-2 text-xs text-alpha-text-muted">
        <Database className="w-3.5 h-3.5 text-alpha-gold/60" />
        <span>Strict zero synthetic data policy enforced</span>
      </div>
    </div>
  );
};
