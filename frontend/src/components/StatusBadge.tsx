import React from 'react';
import { TicketStatus } from '../types/dashboard';

interface StatusBadgeProps {
  status: TicketStatus | string;
  className?: string;
}

const STYLES: Record<string, { label: string; badge: string; dot: string }> = {
  open: { label: 'Open', badge: 'bg-blue-50 text-blue-700 border-blue-200/80', dot: 'bg-blue-500' },
  assigned: { label: 'Assigned', badge: 'bg-indigo-50 text-indigo-700 border-indigo-200/80', dot: 'bg-indigo-500' },
  in_progress: { label: 'In Progress', badge: 'bg-amber-50 text-amber-700 border-amber-200/80', dot: 'bg-amber-500 animate-pulse' },
  pending: { label: 'Pending', badge: 'bg-purple-50 text-purple-700 border-purple-200/80', dot: 'bg-purple-500' },
  resolved: { label: 'Resolved', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200/80', dot: 'bg-emerald-500' },
  closed: { label: 'Closed', badge: 'bg-slate-100 text-slate-700 border-slate-200/80', dot: 'bg-slate-400' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const normalized = (status || '').toLowerCase().replace(/[\s-]/g, '_');
  const style = STYLES[normalized] ?? STYLES.closed;
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${style.badge} ${className}`}
    >
      <span className={`w-1.5 h-1.5 mr-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
};
