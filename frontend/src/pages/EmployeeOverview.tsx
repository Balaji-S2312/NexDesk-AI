import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { getDashboardStatsApi } from '../services/api';
import { EmployeeDashboardData, TicketItem } from '../types/dashboard';
import { KPICard } from '../components/KPICard';
import { DataTable, Column } from '../components/DataTable';
import { StatusBadge } from '../components/StatusBadge';
import { PriorityBadge } from '../components/PriorityBadge';
import { CreateTicketModal } from '../components/CreateTicketModal';
import {
  LifeBuoy,
  Clock,
  CheckCircle2,
  PlusCircle,
  Bot,
  BookOpen,
  ArrowRight,
  Activity,
  Database,
  Calendar,
} from 'lucide-react';

export const EmployeeOverview = () => {
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [data, setData] = useState<EmployeeDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [newTicketModalOpen, setNewTicketModalOpen] = useState(false);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getDashboardStatsApi();
      if (res.role === 'employee') {
        setData(res);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch dashboard metrics';
      showToast({ type: 'error', title: 'Data Loading Error', message: msg });
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const columns: Column<TicketItem>[] = [
    {
      key: 'ticket_number',
      header: 'Ticket',
      className: 'w-28 font-mono text-xs text-[#718096]',
      render: (item) => item.ticket_number ?? `#${item.id}`,
    },
    {
      key: 'title',
      header: 'Incident Title',
      sortable: true,
      className: 'font-semibold text-[#172B3A]',
      render: (item) => (
        <div>
          <div className="font-semibold text-[#172B3A] hover:text-[#087E8B] transition-colors">{item.title}</div>
          <div className="text-[11px] text-[#718096] capitalize">{item.category} Category</div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      className: 'w-32',
      render: (item) => <StatusBadge status={item.status} />,
    },
    {
      key: 'priority',
      header: 'Priority',
      sortable: true,
      className: 'w-28',
      render: (item) => <PriorityBadge priority={item.priority} />,
    },
    {
      key: 'created_at',
      header: 'Created Date',
      sortable: true,
      className: 'w-32 text-[#718096]',
      render: (item) =>
        item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Today',
    },
  ];

  const currentDate = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-[#087E8B] uppercase tracking-wider mb-1">
            <Calendar className="w-3.5 h-3.5" />
            <span>{currentDate}</span>
          </div>
          <h1 className="text-2xl font-bold text-[#172B3A] tracking-tight">
            Good day, {user?.name}
          </h1>
          <p className="text-xs text-[#526773] mt-1">
            Welcome to your enterprise service desk. Track active requests or interact with the AI assistant.
          </p>
        </div>

        {/* Database Sync Pill */}
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-[#EFF3F1] border border-[#DCE4E3] text-xs text-[#172B3A] self-start md:self-auto">
          <Database className="w-3.5 h-3.5 text-[#087E8B]" />
          <span>
            {data?.is_development_baseline
              ? 'Connected to Live SQLite DB (Baseline State)'
              : 'Live Scoped Database Metrics'}
          </span>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <KPICard
          title="Total Requests"
          value={data?.metrics.total_tickets ?? 0}
          icon={<LifeBuoy className="w-5 h-5" />}
          subtitle="All historical requests submitted"
          loading={loading}
          accentColor="teal"
        />
        <KPICard
          title="Active Open Tickets"
          value={data?.metrics.open_tickets ?? 0}
          icon={<Clock className="w-5 h-5" />}
          subtitle="Currently assigned or under triage"
          loading={loading}
          accentColor="amber"
          badgeText="In Queue"
        />
        <KPICard
          title="Resolved Incidents"
          value={data?.metrics.resolved_tickets ?? 0}
          icon={<CheckCircle2 className="w-5 h-5" />}
          subtitle="Successfully closed by IT support"
          loading={loading}
          accentColor="emerald"
        />
      </div>

      {/* Quick Actions Panel */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#526773] mb-4">
          Quick Service Actions
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <button
            onClick={() => setNewTicketModalOpen(true)}
            className="flex items-start space-x-3.5 p-4 rounded-xl border border-[#DCE4E3] hover:border-[#B5E1E4] hover:bg-[#DCEFF0]/30 text-left transition-all group"
          >
            <div className="p-2.5 bg-[#DCEFF0] text-[#087E8B] group-hover:bg-[#087E8B] group-hover:text-white rounded-lg transition-colors">
              <PlusCircle className="w-5 h-5" />
            </div>
            <div>
              <div className="text-sm font-semibold text-[#172B3A] group-hover:text-[#087E8B] transition-colors">
                Raise New Ticket
              </div>
              <p className="text-xs text-[#526773] mt-0.5">Submit hardware, network or software incident</p>
            </div>
          </button>

          <button
            onClick={() => navigate('/ai-support')}
            className="flex items-start space-x-3.5 p-4 rounded-xl border border-[#DCE4E3] hover:border-[#B5E1E4] hover:bg-[#DCEFF0]/30 text-left transition-all group"
          >
            <div className="p-2.5 bg-[#DCEFF0] text-[#087E8B] group-hover:bg-[#087E8B] group-hover:text-white rounded-lg transition-colors">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="text-sm font-semibold text-[#172B3A] group-hover:text-[#087E8B] transition-colors">
                Ask AI Support
              </div>
              <p className="text-xs text-[#526773] mt-0.5">Instant automated runbook troubleshooting</p>
            </div>
          </button>

          <button
            onClick={() => navigate('/knowledge-base')}
            className="flex items-start space-x-3.5 p-4 rounded-xl border border-[#DCE4E3] hover:border-[#C3E4D6] hover:bg-[#EAF5F0]/50 text-left transition-all group"
          >
            <div className="p-2.5 bg-[#EAF5F0] text-[#287A68] group-hover:bg-[#287A68] group-hover:text-white rounded-lg transition-colors">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <div className="text-sm font-semibold text-[#172B3A] group-hover:text-[#287A68] transition-colors">
                Browse Knowledge Base
              </div>
              <p className="text-xs text-[#526773] mt-0.5">Search enterprise SOPs & documentation</p>
            </div>
          </button>
        </div>
      </div>

      {/* Main Grid: Recent Tickets & Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Tickets Table */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-[#172B3A] uppercase tracking-wider">
                My Recent Incidents
              </h2>
              <p className="text-xs text-[#526773]">Tickets submitted under your corporate account</p>
            </div>
            <button
              onClick={() => navigate('/my-tickets')}
              className="text-xs font-semibold text-[#087E8B] hover:text-[#075C66] flex items-center gap-1"
            >
              <span>View all tickets</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <DataTable
            columns={columns}
            data={data?.recent_tickets || []}
            keyExtractor={(item) => item.id}
            loading={loading}
            emptyTitle="No tickets found"
            emptyDescription="You haven't submitted any IT support requests yet."
            emptyActionText="Create your first ticket"
            onEmptyAction={() => setNewTicketModalOpen(true)}
            onRowClick={(item) => navigate(`/tickets/${item.id}`)}
          />
        </div>

        {/* Recent Activity Timeline */}
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-[#087E8B]" />
            <h2 className="text-sm font-bold text-[#172B3A] uppercase tracking-wider">
              Recent Activity
            </h2>
          </div>

          <div className="bg-white rounded-xl border border-[#DCE4E3] p-5 shadow-xs">
            {data?.recent_activity && data.recent_activity.length > 0 ? (
              <div className="space-y-4">
                {data.recent_activity.map((act) => (
                  <div key={act.id} className="flex items-start space-x-3 text-xs">
                    <span className="w-2 h-2 mt-1 rounded-full bg-[#087E8B] shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-[#172B3A]">{act.action.replace('_', ' ')}</div>
                      <div className="text-[#526773] text-[11px] mt-0.5 truncate">{act.details || act.resource_type}</div>
                      <div className="text-[10px] text-[#718096] mt-0.5">
                        {act.created_at ? new Date(act.created_at).toLocaleTimeString() : 'Just now'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-xs text-[#718096]">
                No recent activity logged for your profile.
              </div>
            )}
          </div>
        </div>
      </div>

      <CreateTicketModal
        isOpen={newTicketModalOpen}
        onClose={() => setNewTicketModalOpen(false)}
        onCreated={(ticket) => {
          setNewTicketModalOpen(false);
          window.dispatchEvent(new Event('nexdesk-notifications-updated'));
          navigate(`/tickets/${ticket.id}`);
        }}
      />
    </div>
  );
};
