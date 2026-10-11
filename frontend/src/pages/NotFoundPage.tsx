import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, FileQuestion } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-6">
      <div className="w-16 h-16 rounded-full bg-alpha-gold/10 border border-alpha-gold/20 flex items-center justify-center text-alpha-gold mb-4">
        <FileQuestion className="w-8 h-8" />
      </div>
      <h1 className="text-2xl font-bold font-mono text-alpha-text-primary mb-2">404 - Endpoint Not Found</h1>
      <p className="text-sm text-alpha-text-secondary max-w-sm mb-6">
        The requested routing path is not mounted in the ALPHA Quant system shell.
      </p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg bg-alpha-gold text-black hover:bg-alpha-gold-light transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Return to System Overview</span>
      </Link>
    </div>
  );
};
