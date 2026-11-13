import React from 'react';
import { Filter, RotateCcw } from 'lucide-react';
import { AdaptiveSelect } from './AdaptiveSelect';
import { CategoryIcon } from './CategoryIcon';

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
      <AdaptiveSelect
        size="sm"
        label="Filter by Status"
        ariaLabel="Filter by Status"
        value={statusFilter}
        onChange={onStatusChange}
        className="w-40"
        options={[
          { value: '', label: 'All Statuses' },
          ...statusOptions.map((opt) => ({ value: opt.value, label: opt.label })),
        ]}
      />

      {/* Priority Filter */}
      <AdaptiveSelect
        size="sm"
        label="Filter by Priority"
        ariaLabel="Filter by Priority"
        value={priorityFilter}
        onChange={onPriorityChange}
        className="w-40"
        options={[
          { value: '', label: 'All Priorities' },
          ...priorityOptions.map((opt) => ({ value: opt.value, label: opt.label })),
        ]}
      />

      {/* Category Filter */}
      {categoryOptions && onCategoryChange && (
        <AdaptiveSelect
          size="sm"
          label="Filter by Category"
          ariaLabel="Filter by Category"
          value={categoryFilter || ''}
          onChange={onCategoryChange}
          className="w-48"
          options={[
            { value: '', label: 'All Categories' },
            ...categoryOptions.map((opt) => ({
              value: opt.value,
              label: opt.label,
              icon: <CategoryIcon category={opt.value} className="w-3.5 h-3.5 text-[#087E8B]" />,
            })),
          ]}
        />
      )}

      {/* Reset Filters */}
      {hasActiveFilters && (
        <button
          type="button"
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
