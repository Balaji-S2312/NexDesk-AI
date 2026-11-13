import React from 'react';

interface KPICardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  subtitle?: string;
  trend?: {
    value: string;
    isPositive?: boolean;
    isNeutral?: boolean;
  };
  loading?: boolean;
  accentColor?: 'blue' | 'amber' | 'emerald' | 'rose' | 'purple' | 'slate' | 'teal';
  badgeText?: string;
}

export const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  icon,
  subtitle,
  trend,
  loading = false,
  accentColor = 'teal',
  badgeText,
}) => {
  const getIconBg = () => {
    switch (accentColor) {
      case 'amber':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'emerald':
        return 'bg-[#EAF5F0] text-[#287A68] border-[#C3E4D6]';
      case 'rose':
        return 'bg-rose-50 text-[#C24141] border-rose-200';
      case 'purple':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'slate':
        return 'bg-[#EFF3F1] text-[#526773] border-[#DCE4E3]';
      case 'blue':
      case 'teal':
      default:
        return 'bg-[#DCEFF0] text-[#087E8B] border-[#B5E1E4]';
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-[#DCE4E3] p-5 shadow-xs animate-pulse">
        <div className="flex items-center justify-between mb-3">
          <div className="h-4 w-24 bg-[#EFF3F1] rounded" />
          <div className="h-10 w-10 bg-[#EFF3F1] rounded-lg" />
        </div>
        <div className="h-8 w-16 bg-[#DCE4E3] rounded mb-2" />
        <div className="h-3 w-32 bg-[#EFF3F1] rounded" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-[#DCE4E3] p-5 shadow-xs hover:shadow-sm transition-shadow">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-[#526773] uppercase tracking-wider">{title}</span>
        <div className={`p-2.5 rounded-lg border ${getIconBg()}`}>
          {icon}
        </div>
      </div>

      <div className="flex items-baseline space-x-2">
        <div className="text-2xl font-bold text-[#172B3A] tracking-tight">{value}</div>
        {badgeText && (
          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[#EFF3F1] text-[#172B3A] border border-[#DCE4E3]">
            {badgeText}
          </span>
        )}
      </div>

      {(subtitle || trend) && (
        <div className="mt-2 flex items-center text-xs text-[#526773]">
          {trend && (
            <span
              className={`font-semibold mr-1.5 ${
                trend.isNeutral
                  ? 'text-[#526773]'
                  : trend.isPositive
                  ? 'text-[#287A68]'
                  : 'text-[#C24141]'
              }`}
            >
              {trend.value}
            </span>
          )}
          {subtitle && <span>{subtitle}</span>}
        </div>
      )}
    </div>
  );
};
