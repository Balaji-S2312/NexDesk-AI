import React from 'react';
import { TicketPriority } from '../types/dashboard';

interface PriorityBadgeProps {
  priority: TicketPriority | string;
  className?: string;
}

const STYLES: Record<string, { label: string; badge: string; dot: string }> = {
  critical: { label: 'P1 Critical', badge: 'bg-rose-50 text-rose-700 border-rose-200', dot: 'bg-rose-600' },
  high: { label: 'P2 High', badge: 'bg-orange-50 text-orange-700 border-orange-200', dot: 'bg-orange-500' },
  medium: { label: 'P3 Medium', badge: 'bg-blue-50 text-blue-700 border-blue-200', dot: 'bg-blue-500' },
  low: { label: 'P4 Low', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: 'bg-emerald-500' },
};

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, className = '' }) => {
  const style = STYLES[(priority || '').toLowerCase()] ?? STYLES.low;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${style.badge} ${className}`}
    >
      <span className={`w-1.5 h-1.5 mr-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
};
