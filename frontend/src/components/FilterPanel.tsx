import React from 'react';
import { Filter, RotateCcw } from 'lucide-react';

interface FilterOption {
  label: string;
  value: string;
}

interface FilterPanelProps {
  statusFilter: string;
  onStatusChange: (val: string) => void;
  statusOptions: FilterOption[];
  priorityFilter: string;
  onPriorityChange: (val: string) => void;
  priorityOptions: FilterOption[];
  categoryFilter?: string;
  onCategoryChange?: (val: string) => void;
  categoryOptions?: FilterOption[];
  onReset: () => void;
  hasActiveFilters: boolean;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
  statusFilter,
  onStatusChange,
  statusOptions,
  priorityFilter,
  onPriorityChange,
  priorityOptions,
  categoryFilter,
  onCategoryChange,
  categoryOptions,
  onReset,
  hasActiveFilters,
}) => {
  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <div className="flex items-center text-xs font-semibold text-[#526773] uppercase tracking-wider mr-1">
        <Filter className="w-3.5 h-3.5 mr-1 text-[#718096]" />
        Filters:
      </div>

      {/* Status Filter */}
      <select
        value={statusFilter}
        onChange={(e) => onStatusChange(e.target.value)}
        className="text-xs bg-white border border-[#DCE4E3] rounded-lg px-2.5 py-1.5 text-[#172B3A] font-medium focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] shadow-xs cursor-pointer"
      >
        <option value="">All Statuses</option>
        {statusOptions.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {/* Priority Filter */}
      <select
        value={priorityFilter}
        onChange={(e) => onPriorityChange(e.target.value)}
        className="text-xs bg-white border border-[#DCE4E3] rounded-lg px-2.5 py-1.5 text-[#172B3A] font-medium focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] shadow-xs cursor-pointer"
      >
        <option value="">All Priorities</option>
        {priorityOptions.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {/* Category Filter */}
      {categoryOptions && onCategoryChange && (
        <select
          value={categoryFilter || ''}
          onChange={(e) => onCategoryChange(e.target.value)}
          className="text-xs bg-white border border-[#DCE4E3] rounded-lg px-2.5 py-1.5 text-[#172B3A] font-medium focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] shadow-xs cursor-pointer"
        >
          <option value="">All Categories</option>
          {categoryOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )}

      {/* Reset Filters */}
      {hasActiveFilters && (
        <button
          onClick={onReset}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-[#172B3A] hover:text-[#087E8B] bg-[#EFF3F1] hover:bg-[#DCEFF0] transition-colors"
          title="Reset all filters"
        >
          <RotateCcw className="w-3 h-3" />
          <span>Reset</span>
        </button>
      )}
    </div>
  );
};
