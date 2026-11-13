import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '../hooks/useToast';
import {
  getAnalyticsSummaryApi,
  getTicketTrendsApi,
  getCategoryDistributionApi,
  getPriorityDistributionApi,
  getStatusDistributionApi,
  getGroupWorkloadApi,
  getDashboardStatsApi,
  seedDemoTicketsApi,
} from '../services/api';
import { AdminDashboardData, TicketItem } from '../types/dashboard';
import {
  AnalyticsSummary,
  CategoryDistributionItem,
  PriorityDistributionItem,
  StatusDistributionItem,
  TicketTrendPoint,
  WorkloadItem,
} from '../types/analytics';
import { KPICard } from '../components/KPICard';
import { DataTable, Column } from '../components/DataTable';
import { StatusBadge } from '../components/StatusBadge';
import { PriorityBadge } from '../components/PriorityBadge';
import {
  Flame,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Activity,
  Timer,
  RefreshCw,
  Database,
  Layers,
  PieChart as PieIcon,
  TrendingUp,
  Bell,
  UserCheck,
  Calendar,
  Users,
  BarChart3,
  CheckCircle,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#C24141', // Error red
  high: '#B7791F',     // Warning amber
  medium: '#087E8B',   // Deep teal
  low: '#526773',      // Muted slate
};

export const AdminDashboard: React.FC = () => {
  const { showToast } = useToast();
  const navigate = useNavigate();

  // State
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [trends, setTrends] = useState<TicketTrendPoint[]>([]);
  const [categories, setCategories] = useState<CategoryDistributionItem[]>([]);
  const [priorities, setPriorities] = useState<PriorityDistributionItem[]>([]);
  const [statuses, setStatuses] = useState<StatusDistributionItem[]>([]);
  const [workload, setWorkload] = useState<WorkloadItem[]>([]);
  const [telemetry, setTelemetry] = useState<AdminDashboardData | null>(null);

  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const fetchAllAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, trendRes, catRes, priRes, statRes, workRes, dashRes] = await Promise.all([
        getAnalyticsSummaryApi(dateRange),
        getTicketTrendsApi(dateRange),
        getCategoryDistributionApi(dateRange),
        getPriorityDistributionApi(dateRange),
        getStatusDistributionApi(dateRange),
        getGroupWorkloadApi(dateRange),
        getDashboardStatsApi().catch(() => null),
      ]);

      setSummary(sumRes);
      setTrends(trendRes);
      setCategories(catRes);
      setPriorities(priRes);
      setStatuses(statRes);
      setWorkload(workRes);
      if (dashRes && dashRes.role === 'admin') {
        setTelemetry(dashRes);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch analytics metrics';
      showToast({ type: 'error', title: 'Analytics Error', message: msg });
    } finally {
      setLoading(false);
    }
  }, [dateRange, showToast]);

  useEffect(() => {
    fetchAllAnalytics();
  }, [fetchAllAnalytics]);

  const handleSeedDemoData = async () => {
    setSeeding(true);
    try {
      const res = await seedDemoTicketsApi();
      showToast({ type: 'success', title: 'Demo Incidents Seeded', message: res.message });
      await fetchAllAnalytics();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Seeding failed';
      showToast({ type: 'error', title: 'Seed Error', message: msg });
    } finally {
      setSeeding(false);
    }
  };

  const columns: Column<TicketItem>[] = [
    {
      key: 'ticket_number',
      header: 'Ticket',
      className: 'w-28 font-mono text-xs text-slate-500',
      render: (item) => item.ticket_number ?? `#${item.id}`,
    },
    {
      key: 'title',
      header: 'Incident Title',
      sortable: true,
      className: 'font-semibold text-slate-900',
      render: (item) => (
        <div>
          <div className="font-semibold text-slate-900 hover:text-blue-600 transition-colors">
            {item.title}
          </div>
          <div className="text-[11px] text-slate-400 capitalize">{item.category} Incident</div>
        </div>
      ),
    },
    {
      key: 'requester',
      header: 'Requester',
      sortable: true,
      className: 'text-slate-600',
      render: (item) => item.requester || 'Employee',
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      className: 'w-28',
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
      header: 'Created',
      sortable: true,
      className: 'w-28 text-slate-500',
      render: (item) => (item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Today'),
    },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner & Date Filter */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-blue-600 uppercase tracking-wider mb-1">
            <Activity className="w-3.5 h-3.5" />
            <span>ITSM Command Center &amp; Service Analytics</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Enterprise Service Analytics</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time SQLite analytics, SLA compliance calculation, volume trends, and team workload telemetry.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Date Range Selector */}
          <div className="flex rounded-xl bg-slate-100 p-1 border border-slate-200/80">
            {(
              [
                { id: '7d', label: '7 Days' },
                { id: '30d', label: '30 Days' },
                { id: '90d', label: '90 Days' },
                { id: 'all', label: 'All Time' },
              ] as const
            ).map((btn) => (
              <button
                key={btn.id}
                onClick={() => setDateRange(btn.id)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                  dateRange === btn.id
                    ? 'bg-white text-[#087E8B] shadow-xs'
                    : 'text-[#526773] hover:text-[#172B3A]'
                }`}
              >
                {btn.label}
              </button>
            ))}
          </div>

          {telemetry?.is_development_baseline && (
            <button
              onClick={handleSeedDemoData}
              disabled={seeding}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#DCEFF0] hover:bg-[#b5e1e4] text-[#075C66] border border-[#B5E1E4] text-xs font-semibold transition-colors"
            >
              <Database className="w-3.5 h-3.5 text-[#087E8B]" />
              <span>{seeding ? 'Seeding...' : 'Seed Demo Data'}</span>
            </button>
          )}

          <button
            onClick={fetchAllAnalytics}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-[#EFF3F1] text-[#172B3A] border border-[#DCE4E3] text-xs font-semibold shadow-2xs transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#087E8B]' : 'text-[#718096]'}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 6 Core KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KPICard
          title="Total Tickets"
          value={summary?.total_tickets ?? 0}
          icon={<Flame className="w-4 h-4" />}
          loading={loading}
          accentColor="teal"
        />
        <KPICard
          title="Open Tickets"
          value={summary?.open_tickets ?? 0}
          icon={<Clock className="w-4 h-4" />}
          loading={loading}
          accentColor="rose"
        />
        <KPICard
          title="In Progress"
          value={summary?.in_progress_tickets ?? 0}
          icon={<Layers className="w-4 h-4" />}
          loading={loading}
          accentColor="amber"
        />
        <KPICard
          title="Resolved"
          value={summary?.resolved_tickets ?? 0}
          icon={<CheckCircle2 className="w-4 h-4" />}
          loading={loading}
          accentColor="emerald"
        />
        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-4 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-semibold text-[#526773] mb-1">
            <span>SLA Breaches</span>
            <AlertTriangle className="w-4 h-4 text-[#C24141]" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[#C24141]">{summary?.sla_breaches ?? 0}</span>
            <span className="text-[11px] font-semibold text-[#287A68] bg-[#EAF5F0] px-1.5 py-0.5 rounded">
              {summary ? `${summary.sla_compliance_rate}% comp.` : '—'}
            </span>
          </div>
          <div className="text-[10px] text-[#718096] mt-1">Response or resolution</div>
        </div>
        <KPICard
          title="Avg. Resolution"
          value={summary?.avg_resolution_time_display ?? '0m'}
          icon={<Timer className="w-4 h-4" />}
          loading={loading}
          accentColor="purple"
        />
      </div>

      {/* Primary Analytics Charts: Ticket Trends & Priority Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ticket Volume Trends Chart (Span 2) */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-[#087E8B]" />
              <h3 className="text-xs font-bold text-[#172B3A] uppercase tracking-wider">
                Ticket Trends: Inflow vs. Resolution vs. Breaches
              </h3>
            </div>
            <span className="text-[11px] text-[#526773] flex items-center gap-1 font-mono">
              <Calendar className="w-3 h-3 text-[#087E8B]" /> {dateRange.toUpperCase()} Scope
            </span>
          </div>

          <div className="h-64 w-full">
            {trends.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-[#718096]">
                No trend volume data in this time range.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="createdGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#087E8B" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#087E8B" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="resolvedGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#287A68" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#287A68" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="breachedGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#C24141" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#C24141" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EFF3F1" vertical={false} />
                  <XAxis dataKey="date" stroke="#718096" fontSize={11} tickLine={false} />
                  <YAxis stroke="#718096" fontSize={11} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      borderColor: '#DCE4E3',
                      borderRadius: '8px',
                      fontSize: '11px',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                    }}
                  />
                  <Legend verticalAlign="top" height={30} iconType="circle" wrapperStyle={{ fontSize: '11px' }} />
                  <Area
                    type="monotone"
                    dataKey="created"
                    stroke="#087E8B"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#createdGrad)"
                    name="Created"
                  />
                  <Area
                    type="monotone"
                    dataKey="resolved"
                    stroke="#287A68"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#resolvedGrad)"
                    name="Resolved"
                  />
                  <Area
                    type="monotone"
                    dataKey="breached"
                    stroke="#C24141"
                    strokeWidth={1.5}
                    fillOpacity={1}
                    fill="url(#breachedGrad)"
                    name="Breached"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Priority Distribution Donut */}
        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <PieIcon className="w-4 h-4 text-[#087E8B]" />
              <h3 className="text-xs font-bold text-[#172B3A] uppercase tracking-wider">Priority Distribution</h3>
            </div>
            <span className="text-[11px] text-[#526773]">P1 to P4 Severity</span>
          </div>

          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={priorities}
                  cx="50%"
                  cy="45%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="count"
                  nameKey="priority_label"
                >
                  {priorities.map((entry) => (
                    <Cell
                      key={`cell-${entry.priority}`}
                      fill={PRIORITY_COLORS[entry.priority] || '#718096'}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderColor: '#DCE4E3',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  iconType="circle"
                  wrapperStyle={{ fontSize: '11px', color: '#526773' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Secondary Analytics: Category Distribution & Status Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Breakdown */}
        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <Layers className="w-4 h-4 text-[#087E8B]" />
              <h3 className="text-xs font-bold text-[#172B3A] uppercase tracking-wider">
                Category Distribution
              </h3>
            </div>
            <span className="text-[11px] text-[#526773]">Volume by Domain</span>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categories} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EFF3F1" vertical={false} />
                <XAxis
                  dataKey="category_label"
                  stroke="#718096"
                  fontSize={10}
                  tickLine={false}
                  angle={-20}
                  textAnchor="end"
                />
                <YAxis stroke="#718096" fontSize={11} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderColor: '#DCE4E3',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                />
                <Bar dataKey="count" fill="#087E8B" radius={[6, 6, 0, 0]} name="Tickets" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Status Distribution */}
        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <BarChart3 className="w-4 h-4 text-[#287A68]" />
              <h3 className="text-xs font-bold text-[#172B3A] uppercase tracking-wider">
                Status Pipeline Distribution
              </h3>
            </div>
            <span className="text-[11px] text-[#526773]">Workflow Progression</span>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statuses} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EFF3F1" vertical={false} />
                <XAxis
                  dataKey="status_label"
                  stroke="#718096"
                  fontSize={10}
                  tickLine={false}
                  angle={-20}
                  textAnchor="end"
                />
                <YAxis stroke="#718096" fontSize={11} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderColor: '#DCE4E3',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                />
                <Bar dataKey="count" fill="#287A68" radius={[6, 6, 0, 0]} name="Tickets" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Assignment Group Workload */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Users className="w-4 h-4 text-[#087E8B]" />
            <h3 className="text-xs font-bold text-[#172B3A] uppercase tracking-wider">
              Assignment Group Workload &amp; Capacity
            </h3>
          </div>
          <span className="text-[11px] text-[#526773]">Team Queue Allocations</span>
        </div>

        <div className="h-60 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={workload} margin={{ top: 10, right: 15, left: -20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EFF3F1" vertical={false} />
              <XAxis
                dataKey="group_name"
                stroke="#718096"
                fontSize={10}
                tickLine={false}
                angle={-15}
                textAnchor="end"
              />
              <YAxis stroke="#718096" fontSize={11} tickLine={false} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#ffffff',
                  borderColor: '#DCE4E3',
                  borderRadius: '8px',
                  fontSize: '11px',
                }}
              />
              <Legend verticalAlign="top" height={30} iconType="circle" wrapperStyle={{ fontSize: '11px' }} />
              <Bar dataKey="total_tickets" fill="#087E8B" radius={[4, 4, 0, 0]} name="Total Allocated" />
              <Bar dataKey="open_tickets" fill="#B7791F" radius={[4, 4, 0, 0]} name="Active Open" />
              <Bar dataKey="breached_tickets" fill="#C24141" radius={[4, 4, 0, 0]} name="SLA Breached" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Live Notification & Workflow Activity Telemetry (Module 9A) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-[#172B3A] uppercase tracking-wider flex items-center gap-2">
              <Bell className="w-4 h-4 text-[#087E8B]" /> Recent Notification Alerts
            </h3>
            <button
              type="button"
              onClick={() => navigate('/notifications')}
              className="text-[11px] font-semibold text-[#087E8B] hover:underline"
            >
              View all
            </button>
          </div>
          {!telemetry?.recent_notifications || telemetry.recent_notifications.length === 0 ? (
            <p className="text-xs text-[#718096] py-4">No notification alerts yet.</p>
          ) : (
            <div className="space-y-2.5">
              {telemetry.recent_notifications.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => navigate(n.link || (n.ticket_id ? `/tickets/${n.ticket_id}` : '/notifications'))}
                  className={`w-full text-left p-2.5 rounded-xl border text-xs transition-colors hover:bg-[#EFF3F1] ${
                    !n.is_read ? 'bg-[#DCEFF0]/50 border-[#B5E1E4]' : 'bg-white border-[#DCE4E3]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-[#172B3A] truncate">{n.title}</span>
                    {!n.is_read && <span className="w-2 h-2 rounded-full bg-[#087E8B] shrink-0" />}
                  </div>
                  <div className="text-[11px] text-[#526773] mt-0.5 line-clamp-2">{n.message}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs space-y-3">
          <h3 className="text-xs font-bold text-[#172B3A] uppercase tracking-wider flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-[#087E8B]" /> Recently Assigned Incidents
          </h3>
          {!telemetry?.recently_assigned_incidents || telemetry.recently_assigned_incidents.length === 0 ? (
            <p className="text-xs text-[#718096] py-4">No assigned incidents yet.</p>
          ) : (
            <div className="space-y-2.5">
              {telemetry.recently_assigned_incidents.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => navigate(`/tickets/${t.id}`)}
                  className="w-full text-left p-2.5 rounded-xl border border-[#DCE4E3] hover:bg-[#EFF3F1] text-xs transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono font-semibold text-[#087E8B]">{t.ticket_number}</span>
                    <span className="px-2 py-0.5 rounded bg-[#DCEFF0] text-[#075C66] text-[10px] font-semibold">
                      {t.assigned_group}
                    </span>
                  </div>
                  <div className="font-medium text-[#172B3A] truncate mt-1">{t.title}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs space-y-3">
          <h3 className="text-xs font-bold text-[#172B3A] uppercase tracking-wider flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-[#287A68]" /> Recently Resolved Incidents
          </h3>
          {!telemetry?.recently_resolved_incidents || telemetry.recently_resolved_incidents.length === 0 ? (
            <p className="text-xs text-[#718096] py-4">No resolved incidents yet.</p>
          ) : (
            <div className="space-y-2.5">
              {telemetry.recently_resolved_incidents.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => navigate(`/tickets/${t.id}`)}
                  className="w-full text-left p-2.5 rounded-xl border border-[#C3E4D6] bg-[#EAF5F0]/60 hover:bg-[#EAF5F0] text-xs transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono font-semibold text-[#287A68]">{t.ticket_number}</span>
                    <StatusBadge status={t.status} />
                  </div>
                  <div className="font-medium text-[#172B3A] truncate mt-1">{t.title}</div>
                  {t.resolution_notes && (
                    <div className="text-[11px] text-[#526773] truncate mt-0.5">{t.resolution_notes}</div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Incidents Table */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-[#172B3A] uppercase tracking-wider">
              Organization Recent Incidents
            </h2>
            <p className="text-xs text-[#526773]">Live operational queue across all support tiers</p>
          </div>
        </div>

        <DataTable
          columns={columns}
          data={telemetry?.recent_incidents || []}
          keyExtractor={(item) => item.id}
          loading={loading}
          emptyTitle="No incidents logged"
          emptyDescription="The incident database is currently clean."
          emptyActionText="Load sample incidents"
          onEmptyAction={handleSeedDemoData}
          onRowClick={(item) => navigate(`/tickets/${item.id}`)}
        />
      </div>
    </div>
  );
};
