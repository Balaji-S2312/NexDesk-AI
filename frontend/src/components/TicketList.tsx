import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, PlusCircle, RefreshCw, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useToast } from '../hooks/useToast';
import { listAssignmentGroupsApi, listTicketsApi } from '../services/api';
import { AssignmentGroup, Ticket } from '../types/ticket';
import { DataTable, Column } from './DataTable';
import { StatusBadge } from './StatusBadge';
import { PriorityBadge } from './PriorityBadge';
import { SearchBar } from './SearchBar';
import { FilterPanel } from './FilterPanel';
import { CreateTicketModal } from './CreateTicketModal';
import { CATEGORY_OPTIONS, PRIORITY_OPTIONS, STATUS_OPTIONS, formatDateTime, labelFor } from '../utils/ticketOptions';

interface TicketListProps {
  scope: 'mine' | 'all';
  title: string;
  subtitle: string;
}

const PAGE_SIZE = 15;

const selectCls =
  'text-xs bg-white border border-[#DCE4E3] rounded-lg px-2.5 py-1.5 text-[#172B3A] font-medium focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] shadow-xs cursor-pointer';

export const TicketList: React.FC<TicketListProps> = ({ scope, title, subtitle }) => {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [groupFilter, setGroupFilter] = useState('');
  const [groups, setGroups] = useState<AssignmentGroup[]>([]);
  const [createOpen, setCreateOpen] = useState(false);

  // Debounce search so we don't hit the API on every keystroke.
  useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(handle);
  }, [search]);

  useEffect(() => {
    if (scope !== 'all') return;
    listAssignmentGroupsApi()
      .then(setGroups)
      .catch(() => setGroups([]));
  }, [scope]);

  const fetchTickets = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await listTicketsApi({
        q: debouncedSearch,
        status: statusFilter,
        priority: priorityFilter,
        category: categoryFilter,
        group_id: groupFilter ? Number(groupFilter) : undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setTickets(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load tickets';
      setLoadError(msg);
      showToast({ type: 'error', title: 'Could not load tickets', message: msg });
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, statusFilter, priorityFilter, categoryFilter, groupFilter, page, showToast]);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  const hasActiveFilters = !!(statusFilter || priorityFilter || categoryFilter || groupFilter);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const resetFilters = () => {
    setStatusFilter('');
    setPriorityFilter('');
    setCategoryFilter('');
    setGroupFilter('');
    setPage(1);
  };

  const columns: Column<Ticket>[] = [
    {
      key: 'ticket_number',
      header: 'Ticket',
      className: 'w-28 font-mono text-xs text-slate-500',
      render: (t) => t.ticket_number,
    },
    {
      key: 'title',
      header: 'Title',
      render: (t) => (
        <div>
          <div className="font-semibold text-[#172B3A] hover:text-[#087E8B] transition-colors">{t.title}</div>
          <div className="text-[11px] text-[#718096] flex flex-wrap items-center gap-1.5 mt-0.5">
            <span>
              {labelFor(CATEGORY_OPTIONS, t.category)}
              {t.subcategory ? ` / ${t.subcategory}` : ''}
              {scope === 'all' && t.created_by ? ` • ${t.created_by}` : ''}
            </span>
            {(t.status === 'resolved' || t.status === 'closed' || t.resolution_notes) && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#EAF5F0] text-[#287A68] border border-[#C3E4D6] text-[10px] font-semibold">
                <CheckCircle2 className="w-3 h-3" />
                {t.resolution_notes ? 'Resolution Notes Ready' : 'Resolved'}
              </span>
            )}
          </div>
        </div>
      ),
    },
    { key: 'status', header: 'Status', className: 'w-32', render: (t) => <StatusBadge status={t.status} /> },
    { key: 'priority', header: 'Priority', className: 'w-32', render: (t) => <PriorityBadge priority={t.priority} /> },
    {
      key: 'assigned_group',
      header: 'Group',
      className: 'w-44 text-slate-600',
      render: (t) => t.assigned_group ?? <span className="text-slate-400">Unassigned</span>,
    },
    {
      key: 'sla_deadline',
      header: 'SLA Deadline',
      className: 'w-44 text-slate-600',
      render: (t) => (
        <span className={t.sla_breached ? 'text-rose-600 font-semibold inline-flex items-center gap-1' : ''}>
          {t.sla_breached && <AlertTriangle className="w-3 h-3" />}
          {formatDateTime(t.sla_deadline)}
        </span>
      ),
    },
    {
      key: 'updated_at',
      header: 'Last Updated',
      className: 'w-44 text-slate-500',
      render: (t) => (
        <div>
          <div className="text-slate-700">{formatDateTime(t.updated_at || t.created_at)}</div>
          <div className="text-[10px] text-slate-400">Created {formatDateTime(t.created_at)}</div>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#172B3A] tracking-tight">{title}</h1>
          <p className="text-xs text-[#526773] mt-1">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            onClick={fetchTickets}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-white hover:bg-[#EFF3F1] text-[#172B3A] border border-[#DCE4E3] text-xs font-semibold shadow-2xs transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#087E8B]' : 'text-[#718096]'}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setCreateOpen(true)}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg bg-[#087E8B] hover:bg-[#075C66] text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Create Ticket</span>
          </button>
        </div>
      </div>

      <div className="space-y-3">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder={
            scope === 'all'
              ? 'Search by ticket number, title, description or requester...'
              : 'Search by ticket number, title or description...'
          }
        />
        <div className="flex flex-wrap items-center gap-2.5">
          <FilterPanel
            statusFilter={statusFilter}
            onStatusChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            statusOptions={STATUS_OPTIONS}
            priorityFilter={priorityFilter}
            onPriorityChange={(v) => {
              setPriorityFilter(v);
              setPage(1);
            }}
            priorityOptions={PRIORITY_OPTIONS}
            categoryFilter={categoryFilter}
            onCategoryChange={(v) => {
              setCategoryFilter(v);
              setPage(1);
            }}
            categoryOptions={CATEGORY_OPTIONS}
            hasActiveFilters={hasActiveFilters}
            onReset={resetFilters}
          />
          {scope === 'all' && (
            <select
              value={groupFilter}
              onChange={(e) => {
                setGroupFilter(e.target.value);
                setPage(1);
              }}
              className={selectCls}
            >
              <option value="">All Groups</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {loadError && !loading && (
        <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
          {loadError}
        </div>
      )}

      <DataTable
        columns={columns}
        data={tickets}
        keyExtractor={(t) => t.id}
        loading={loading}
        pageSize={PAGE_SIZE}
        emptyTitle={debouncedSearch || hasActiveFilters ? 'No matching tickets' : 'No tickets yet'}
        emptyDescription={
          debouncedSearch || hasActiveFilters
            ? 'Try different search terms or reset the filters.'
            : 'Create a ticket to get started.'
        }
        emptyActionText={debouncedSearch || hasActiveFilters ? undefined : 'Create ticket'}
        onEmptyAction={() => setCreateOpen(true)}
        onRowClick={(t) => navigate(`/tickets/${t.id}`)}
      />

      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>
          {total} ticket{total === 1 ? '' : 's'} • Page {page} of {totalPages}
        </span>
        <div className="flex items-center gap-2">
          <button
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="p-1.5 rounded-lg border border-slate-200 bg-white disabled:opacity-40 hover:bg-slate-50"
            title="Previous page"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => p + 1)}
            className="p-1.5 rounded-lg border border-slate-200 bg-white disabled:opacity-40 hover:bg-slate-50"
            title="Next page"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      <CreateTicketModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(ticket) => {
          setCreateOpen(false);
          window.dispatchEvent(new Event('nexdesk-notifications-updated'));
          navigate(`/tickets/${ticket.id}`);
        }}
      />
    </div>
  );
};
