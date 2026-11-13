import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { HealthResponse } from '../types/api';

interface HealthBadgeProps {
  health: HealthResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export const HealthBadge: React.FC<HealthBadgeProps> = ({
  health,
  loading,
  error,
  onRefresh,
}) => {
  if (loading) {
    return (
      <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-600 text-xs">
        <RefreshCw className="w-3 h-3 animate-spin text-blue-600" />
        <span className="hidden sm:inline">Checking API...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center space-x-2 px-2.5 py-1 rounded-full bg-rose-50 border border-rose-200 text-rose-700 text-xs">
        <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
        <span className="font-medium hidden sm:inline">API Offline</span>
        <button
          onClick={onRefresh}
          className="hover:underline font-bold text-rose-800"
          title="Retry connection"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div
      className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs cursor-pointer hover:bg-emerald-100 transition-colors"
      onClick={onRefresh}
      title={`Connected to ${health?.app_name} (${health?.environment})`}
    >
      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
      <span className="font-semibold hidden sm:inline">Live Gateway</span>
      <span className="text-emerald-700 font-mono text-[11px]">v{health?.version}</span>
    </div>
  );
};
