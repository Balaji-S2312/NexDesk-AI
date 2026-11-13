import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '../hooks/useToast';
import {
  Clock,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Plus,
  RefreshCw,
  ExternalLink,
  Edit2,
  Info,
  Timer,
  Zap,
} from 'lucide-react';
import { Modal } from '../components/Modal';
import { PriorityBadge } from '../components/PriorityBadge';
import { StatusBadge } from '../components/StatusBadge';
import {
  getSLAOverviewApi,
  listSLAPoliciesApi,
  createSLAPolicyApi,
  updateSLAPolicyApi,
} from '../services/api';
import { SLAOverview, SLAPolicy, SLAIncidentItem } from '../types/sla';
import { PriorityValue, StatusValue } from '../types/ticket';

export const AdminSLAManagement: React.FC = () => {
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [overview, setOverview] = useState<SLAOverview | null>(null);
  const [policies, setPolicies] = useState<SLAPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overdue' | 'breached'>('overdue');

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<SLAPolicy | null>(null);
  const [formName, setFormName] = useState('');
  const [formPriority, setFormPriority] = useState<'critical' | 'high' | 'medium' | 'low'>('medium');
  const [formResponseMinutes, setFormResponseMinutes] = useState(240);
  const [formResolutionHours, setFormResolutionHours] = useState(24);
  const [formBusinessHoursOnly, setFormBusinessHoursOnly] = useState(false);
  const [formEscalationContact, setFormEscalationContact] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewData, policiesData] = await Promise.all([
        getSLAOverviewApi(),
        listSLAPoliciesApi(),
      ]);
      setOverview(overviewData);
      setPolicies(policiesData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load SLA governance metrics';
      showToast({ type: 'error', title: 'SLA Telemetry Error', message: msg });
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenCreate = () => {
    setEditingPolicy(null);
    setFormName('');
    setFormPriority('medium');
    setFormResponseMinutes(240);
    setFormResolutionHours(24);
    setFormBusinessHoursOnly(true);
    setFormEscalationContact('servicedesk@nexdesk.ai');
    setModalOpen(true);
  };

  const handleOpenEdit = (p: SLAPolicy) => {
    setEditingPolicy(p);
    setFormName(p.name);
    setFormPriority(p.priority);
    setFormResponseMinutes(p.response_time_minutes || (p.response_time_hours ? Math.round(p.response_time_hours * 60) : 240));
    setFormResolutionHours(p.resolution_time_hours);
    setFormBusinessHoursOnly(p.business_hours_only);
    setFormEscalationContact(p.escalation_contact || '');
    setModalOpen(true);
  };

  const handleSavePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      showToast({ type: 'warning', title: 'Validation Warning', message: 'Policy name is required.' });
      return;
    }

    setSaving(true);
    try {
      if (editingPolicy) {
        await updateSLAPolicyApi(editingPolicy.id, {
          name: formName,
          response_time_minutes: Number(formResponseMinutes),
          resolution_time_hours: Number(formResolutionHours),
          business_hours_only: formBusinessHoursOnly,
          escalation_contact: formEscalationContact.trim() || undefined,
        });
        showToast({
          type: 'success',
          title: 'Policy Updated',
          message: `SLA policy "${formName}" updated successfully.`,
        });
      } else {
        await createSLAPolicyApi({
          name: formName,
          priority: formPriority,
          response_time_minutes: Number(formResponseMinutes),
          resolution_time_hours: Number(formResolutionHours),
          business_hours_only: formBusinessHoursOnly,
          escalation_contact: formEscalationContact.trim() || undefined,
        });
        showToast({
          type: 'success',
          title: 'Policy Created',
          message: `New SLA policy "${formName}" registered.`,
        });
      }
      setModalOpen(false);
      await fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save SLA policy';
      showToast({ type: 'error', title: 'Save Failed', message: msg });
    } finally {
      setSaving(false);
    }
  };

  const formatMinutesDisplay = (minutes: number) => {
    if (minutes < 60) {
      return `${minutes} Minutes`;
    }
    const hrs = minutes / 60;
    return hrs % 1 === 0 ? `${hrs} Hours` : `${hrs.toFixed(1)} Hours (${minutes}m)`;
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-[#087E8B] uppercase tracking-wider mb-1">
            <Clock className="w-3.5 h-3.5" />
            <span>Service Level Agreements &amp; Governance</span>
          </div>
          <h1 className="text-2xl font-bold text-[#172B3A] tracking-tight">SLA Management &amp; Breach Telemetry</h1>
          <p className="text-xs text-[#526773] mt-1">
            Real-time compliance monitoring, response &amp; resolution deadlines, business calendar governance, and escalations.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-[#EFF3F1] text-[#172B3A] border border-[#DCE4E3] text-xs font-semibold shadow-2xs transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#087E8B]' : 'text-[#718096]'}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={handleOpenCreate}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-[#087E8B] hover:bg-[#075C66] text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>New SLA Policy</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-2">
            <span>Overall Compliance</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">
            {overview ? `${overview.overall_compliance_rate}%` : '—'}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {overview?.total_evaluated ?? 0} total evaluated
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-2">
            <span>Response SLA</span>
            <Zap className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-blue-600">
            {overview ? `${overview.response_compliance_rate}%` : '—'}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">First response targets</div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-2">
            <span>Resolution SLA</span>
            <Timer className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-indigo-600">
            {overview ? `${overview.resolution_compliance_rate}%` : '—'}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Mean resolution compliance</div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-2">
            <span>Overdue Incidents</span>
            <AlertTriangle className="w-4 h-4 text-rose-600" />
          </div>
          <div className="text-2xl font-bold text-rose-600">
            {overview?.total_overdue ?? 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Active past resolution deadline</div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-2">
            <span>Total Breaches</span>
            <ShieldAlert className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl font-bold text-amber-600">
            {overview?.total_breached ?? 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Response or resolution</div>
        </div>
      </div>

      {/* SLA Policies Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight">Active SLA Policy Matrix</h2>
            <p className="text-xs text-slate-500">
              Deterministic ITIL priority thresholds, response targets, and calendar clock modes.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {policies.map((p) => {
            const isP1 = p.priority === 'critical';
            const metrics = overview?.policies.find((m) => m.policy.id === p.id);
            return (
              <div
                key={p.id}
                className={`bg-white rounded-2xl border p-5 shadow-xs flex flex-col justify-between transition-all ${
                  isP1 ? 'border-rose-200 ring-1 ring-rose-100' : 'border-slate-200'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div>
                      <PriorityBadge priority={p.priority as PriorityValue} />
                      <h3 className="font-bold text-slate-900 text-sm mt-1.5">{p.name}</h3>
                    </div>
                    <button
                      onClick={() => handleOpenEdit(p)}
                      className="text-slate-400 hover:text-blue-600 p-1 rounded-md transition-colors"
                      title="Edit Policy"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div className="space-y-2 p-3 bg-slate-50 rounded-xl mb-3 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-500 text-[11px]">Response Target</span>
                      <span className="font-bold text-slate-900">
                        {formatMinutesDisplay(p.response_time_minutes)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-500 text-[11px]">Resolution Target</span>
                      <span className="font-bold text-slate-900">{p.resolution_time_hours} Hours</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-500 text-[11px]">Clock Model</span>
                      <span className="font-semibold text-slate-700 text-[11px]">
                        {p.business_hours_only ? '9x5 Business Hours' : '24x7 Continuous'}
                      </span>
                    </div>
                    {p.escalation_contact && (
                      <div className="pt-1 border-t border-slate-200/60 text-[10px] text-slate-400 truncate">
                        Escalates: {p.escalation_contact}
                      </div>
                    )}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">
                    Active: <strong className="text-slate-800">{metrics?.active_tickets ?? 0}</strong>
                  </span>
                  <span
                    className={`font-semibold ${
                      (metrics?.compliance_rate ?? 100) >= 90
                        ? 'text-emerald-600'
                        : 'text-amber-600'
                    }`}
                  >
                    {metrics ? `${metrics.compliance_rate}% comp.` : '100% comp.'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Calendar vs Business Time Notice */}
      <div className="bg-blue-50/60 border border-blue-200/80 rounded-2xl p-5 flex items-start space-x-3.5 text-xs text-blue-900">
        <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="font-bold text-blue-950">
            SLA Calculation Standard: Calendar Time vs. Business Hours
          </div>
          <p className="text-blue-800 leading-relaxed">
            <strong>24x7 Continuous Calendar Time:</strong> Elapsed continuously across nights, weekends, and holidays. Standard for P1 Critical Outages and P2 Major Degradations where operational response is continuous.
          </p>
          <p className="text-blue-800 leading-relaxed">
            <strong>9x5 Business Hours:</strong> Clocks run Monday through Friday, 09:00 to 17:00 UTC. Non-business hours and weekend time (Saturday &amp; Sunday) are automatically excluded from the SLA deadline calculation for P3 Standard Requests and P4 Minor Inquiries.
          </p>
        </div>
      </div>

      {/* Incidents Telemetry Table: Overdue & Breached */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight">
              SLA Incident Telemetry &amp; At-Risk Incidents
            </h2>
            <p className="text-xs text-slate-500">
              Live monitoring of incidents approaching or exceeding response/resolution deadlines.
            </p>
          </div>

          <div className="flex rounded-xl bg-slate-100 p-1">
            <button
              onClick={() => setActiveTab('overdue')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
                activeTab === 'overdue'
                  ? 'bg-white text-rose-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Overdue Incidents ({overview?.overdue_incidents.length ?? 0})</span>
            </button>
            <button
              onClick={() => setActiveTab('breached')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
                activeTab === 'breached'
                  ? 'bg-white text-amber-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>All Breached Incidents ({overview?.recent_breaches.length ?? 0})</span>
            </button>
          </div>
        </div>

        {/* Incidents List */}
        {(() => {
          const list: SLAIncidentItem[] =
            activeTab === 'overdue'
              ? overview?.overdue_incidents || []
              : overview?.recent_breaches || [];

          if (list.length === 0) {
            return (
              <div className="text-center py-12 border border-dashed border-slate-200 rounded-xl">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                <h4 className="text-sm font-bold text-slate-800">
                  {activeTab === 'overdue' ? 'Zero Overdue Incidents' : 'No SLA Breaches'}
                </h4>
                <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                  All active incidents are currently tracking within their response and resolution thresholds.
                </p>
              </div>
            );
          }

          return (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-400 uppercase font-semibold text-[10px]">
                    <th className="py-2.5 px-3">Ticket</th>
                    <th className="py-2.5 px-3">Title</th>
                    <th className="py-2.5 px-3">Priority</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Assignment Group</th>
                    <th className="py-2.5 px-3">Age</th>
                    <th className="py-2.5 px-3">Resolution Deadline</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {list.map((inc) => (
                    <tr
                      key={inc.id}
                      onClick={() => navigate(`/tickets/${inc.id}`)}
                      className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-3 font-mono font-semibold text-blue-600">
                        {inc.ticket_number}
                      </td>
                      <td className="py-3 px-3 font-medium text-slate-900 max-w-xs truncate">
                        {inc.title}
                      </td>
                      <td className="py-3 px-3">
                        <PriorityBadge priority={inc.priority as PriorityValue} />
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={inc.status as StatusValue} />
                      </td>
                      <td className="py-3 px-3 text-slate-600">
                        {inc.assigned_group || 'Unassigned'}
                      </td>
                      <td className="py-3 px-3 font-semibold text-slate-700">
                        {inc.ticket_age_display}
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-rose-600 font-semibold inline-flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          {inc.resolution_deadline
                            ? new Date(inc.resolution_deadline).toLocaleString()
                            : 'Passed'}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/tickets/${inc.id}`);
                          }}
                          className="text-blue-600 hover:text-blue-800 font-semibold inline-flex items-center gap-1 text-[11px]"
                        >
                          View <ExternalLink className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })()}
      </div>

      {/* Policy Create / Edit Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingPolicy ? 'Edit SLA Policy' : 'Create SLA Policy'}
        description="Configure target response times, resolution thresholds, and business calendar hours."
        footer={
          <>
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="sla-modal-form"
              disabled={saving}
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs"
            >
              {saving ? 'Saving...' : editingPolicy ? 'Update Policy' : 'Create Policy'}
            </button>
          </>
        }
      >
        <form id="sla-modal-form" onSubmit={handleSavePolicy} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Policy Name</label>
            <input
              type="text"
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. P1 - Critical Outage SLA"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Target Priority</label>
              <select
                value={formPriority}
                disabled={Boolean(editingPolicy)}
                onChange={(e) => setFormPriority(e.target.value as 'critical' | 'high' | 'medium' | 'low')}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white disabled:bg-slate-100"
              >
                <option value="critical">Critical (P1)</option>
                <option value="high">High (P2)</option>
                <option value="medium">Medium (P3)</option>
                <option value="low">Low (P4)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Escalation Contact</label>
              <input
                type="text"
                value={formEscalationContact}
                onChange={(e) => setFormEscalationContact(e.target.value)}
                placeholder="ops-escalations@nexdesk.ai"
                className="w-full px-3 py-2 border border-slate-200 rounded-lg"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Response Target (Minutes)
              </label>
              <input
                type="number"
                min="1"
                required
                value={formResponseMinutes}
                onChange={(e) => setFormResponseMinutes(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg"
              />
              <span className="text-[10px] text-slate-400 mt-0.5 block">
                {formatMinutesDisplay(formResponseMinutes)}
              </span>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Resolution Target (Hours)
              </label>
              <input
                type="number"
                min="1"
                required
                value={formResolutionHours}
                onChange={(e) => setFormResolutionHours(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg"
              />
              <span className="text-[10px] text-slate-400 mt-0.5 block">
                {formResolutionHours} Hours from creation
              </span>
            </div>
          </div>

          <div className="pt-2">
            <label className="flex items-center space-x-2 text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                checked={formBusinessHoursOnly}
                onChange={(e) => setFormBusinessHoursOnly(e.target.checked)}
                className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4"
              />
              <span className="font-semibold">Business Hours Only (9:00 - 17:00 M-F)</span>
            </label>
            <p className="text-[11px] text-slate-400 ml-6 mt-0.5">
              When checked, weekends and outside-business hours do not count against the response/resolution timers.
            </p>
          </div>
        </form>
      </Modal>
    </div>
  );
};
