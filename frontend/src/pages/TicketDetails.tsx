import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  Bell,
  BookOpen,
  CheckCircle2,
  Clock,
  History,
  Mail,
  Save,
  ShieldAlert,
  Wrench,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import {
  getTicketApi,
  getTicketHistoryApi,
  listAgentEscalationsApi,
  listAssignmentGroupsApi,
  listEmailHistoryApi,
  listNotificationsApi,
  overrideTicketRecommendationApi,
  updateTicketApi,
} from '../services/api';
import { AgentEscalationRecord } from '../types/agent';
import { EmailDeliveryLogItem, NotificationItem } from '../types/notification';
import {
  AssignmentGroup,
  ImpactLevel,
  StatusValue,
  Ticket,
  TicketCategoryValue,
  TicketHistoryEntry,
  TicketUpdatePayload,
  UrgencyLevel,
} from '../types/ticket';
import { StatusBadge } from '../components/StatusBadge';
import { PriorityBadge } from '../components/PriorityBadge';
import { ConfirmationDialog } from '../components/ConfirmationDialog';
import { Skeleton } from '../components/LoadingSkeleton';
import { AdaptiveSelect } from '../components/AdaptiveSelect';
import { CategoryIcon } from '../components/CategoryIcon';
import {
  CATEGORY_OPTIONS,
  FIELD_LABELS,
  IMPACT_OPTIONS,
  STATUS_OPTIONS,
  URGENCY_OPTIONS,
  formatDateTime,
  labelFor,
  previewPriority,
} from '../utils/ticketOptions';

const inputCls =
  'w-full text-xs px-3 py-2 border border-[#DCE4E3] rounded-lg bg-white text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] transition-colors';

const prettyValue = (field: string, value: string | null): string => {
  if (value === null || value === '') return '—';
  switch (field) {
    case 'status':
      return labelFor(STATUS_OPTIONS, value);
    case 'category':
      return labelFor(CATEGORY_OPTIONS, value);
    case 'impact':
    case 'urgency':
      return value.charAt(0).toUpperCase() + value.slice(1);
    case 'sla_deadline':
      return formatDateTime(value);
    default:
      return value;
  }
};

export const TicketDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const ticketId = Number(id);
  const { isAdmin } = useAuth();
  const { showToast } = useToast();

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [history, setHistory] = useState<TicketHistoryEntry[]>([]);
  const [escalations, setEscalations] = useState<AgentEscalationRecord[]>([]);
  const [ticketNotifications, setTicketNotifications] = useState<NotificationItem[]>([]);
  const [ticketEmailLogs, setTicketEmailLogs] = useState<EmailDeliveryLogItem[]>([]);
  const [groups, setGroups] = useState<AssignmentGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // admin edit form
  const [status, setStatus] = useState<StatusValue>('open');
  const [groupId, setGroupId] = useState('');
  const [category, setCategory] = useState<TicketCategoryValue>('other');
  const [impact, setImpact] = useState<ImpactLevel>('medium');
  const [urgency, setUrgency] = useState<UrgencyLevel>('medium');
  const [notes, setNotes] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [closeOpen, setCloseOpen] = useState(false);

  const syncForm = (t: Ticket) => {
    setStatus(t.status);
    setGroupId(t.group_id ? String(t.group_id) : '');
    setCategory(t.category);
    setImpact(t.impact);
    setUrgency(t.urgency);
    setNotes(t.resolution_notes ?? '');
  };

  const load = useCallback(async () => {
    if (!Number.isInteger(ticketId) || ticketId <= 0) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [t, h, esc, notifs, emails] = await Promise.all([
        getTicketApi(ticketId),
        getTicketHistoryApi(ticketId),
        listAgentEscalationsApi({ ticket_id: ticketId }).catch(() => []),
        listNotificationsApi({ ticket_id: ticketId, limit: 20 }).catch(() => ({ items: [], total: 0, unread_count: 0 })),
        listEmailHistoryApi({ ticket_id: ticketId, limit: 20 }).catch(() => []),
      ]);
      setTicket(t);
      setHistory(h);
      setEscalations(esc);
      setTicketNotifications(notifs.items);
      setTicketEmailLogs(emails);
      syncForm(t);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load ticket';
      if (msg.toLowerCase().includes('not found')) setNotFound(true);
      else setLoadError(msg);
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!isAdmin) return;
    listAssignmentGroupsApi()
      .then(setGroups)
      .catch(() => setGroups([]));
  }, [isAdmin]);

  const applyUpdate = async (payload: TicketUpdatePayload, successMsg: string) => {
    if (!ticket) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateTicketApi(ticket.id, payload);
      setTicket(updated);
      syncForm(updated);
      const [h, notifs, emails] = await Promise.all([
        getTicketHistoryApi(ticket.id),
        listNotificationsApi({ ticket_id: ticket.id, limit: 20 }).catch(() => ({ items: [], total: 0, unread_count: 0 })),
        listEmailHistoryApi({ ticket_id: ticket.id, limit: 20 }).catch(() => []),
      ]);
      setHistory(h);
      setTicketNotifications(notifs.items);
      setTicketEmailLogs(emails);
      window.dispatchEvent(new Event('nexdesk-notifications-updated'));
      showToast({ type: 'success', title: 'Ticket updated', message: successMsg });
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticket) return;
    const payload: TicketUpdatePayload = {};
    if (status !== ticket.status) payload.status = status;
    const newGroup = groupId ? Number(groupId) : null;
    if (newGroup !== ticket.group_id) payload.group_id = newGroup;
    if (category !== ticket.category) payload.category = category;
    if (impact !== ticket.impact) payload.impact = impact;
    if (urgency !== ticket.urgency) payload.urgency = urgency;
    if (notes.trim() !== (ticket.resolution_notes ?? '')) payload.resolution_notes = notes.trim() || null;

    if (Object.keys(payload).length === 0) {
      showToast({ type: 'info', title: 'No changes', message: 'Nothing to save.' });
      return;
    }

    if (overrideReason.trim()) {
      setSaving(true);
      setSaveError(null);
      try {
        if (payload.resolution_notes !== undefined) {
          await updateTicketApi(ticket.id, { resolution_notes: payload.resolution_notes });
        }
        const res = await overrideTicketRecommendationApi(ticket.id, {
          status: payload.status,
          group_id: typeof payload.group_id === 'number' ? payload.group_id : undefined,
          category: payload.category,
          impact: payload.impact,
          urgency: payload.urgency,
          override_reason: overrideReason.trim(),
        });
        setTicket(res.ticket);
        syncForm(res.ticket);
        setOverrideReason('');
        const [h, notifs, emails] = await Promise.all([
          getTicketHistoryApi(ticket.id),
          listNotificationsApi({ ticket_id: ticket.id, limit: 20 }).catch(() => ({ items: [], total: 0, unread_count: 0 })),
          listEmailHistoryApi({ ticket_id: ticket.id, limit: 20 }).catch(() => []),
        ]);
        setHistory(h);
        setTicketNotifications(notifs.items);
        setTicketEmailLogs(emails);
        window.dispatchEvent(new Event('nexdesk-notifications-updated'));
        showToast({
          type: 'success',
          title: 'AI recommendation overridden',
          message: `Recorded ${res.changes_count} audited override change(s).`,
        });
      } catch (err: unknown) {
        setSaveError(err instanceof Error ? err.message : 'Override failed');
      } finally {
        setSaving(false);
      }
      return;
    }

    await applyUpdate(payload, `${ticket.ticket_number} saved.`);
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (notFound || !ticket) {
    return (
      <div className="max-w-xl mx-auto text-center bg-white border border-slate-200 rounded-2xl p-10 shadow-xs">
        <h1 className="text-lg font-bold text-slate-900">{loadError ? 'Unable to load ticket' : 'Ticket not found'}</h1>
        <p className="text-xs text-slate-500 mt-1">
          {loadError ?? 'It may not exist, or you do not have access to it.'}
        </p>
        <Link
          to={isAdmin ? '/incidents' : '/my-tickets'}
          className="inline-block mt-4 text-xs font-semibold text-blue-600 hover:text-blue-700"
        >
          Back to tickets
        </Link>
      </div>
    );
  }

  const previewed = previewPriority(impact, urgency);
  const backTo = isAdmin ? '/incidents' : '/my-tickets';

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <Link to={backTo} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-blue-600">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to {isAdmin ? 'all incidents' : 'my tickets'}
        </Link>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-3 mt-2">
          <div>
            <div className="text-xs font-mono text-slate-500">{ticket.ticket_number}</div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{ticket.title}</h1>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <PriorityBadge priority={ticket.priority} />
            <StatusBadge status={ticket.status} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Details */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-5">
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">Description</h2>
              <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{ticket.description}</p>
            </div>

            <dl className="grid grid-cols-2 md:grid-cols-3 gap-4 text-xs">
              <div>
                <dt className="text-slate-400">Category</dt>
                <dd className="font-semibold text-slate-800">
                  {labelFor(CATEGORY_OPTIONS, ticket.category)}
                  {ticket.subcategory ? ` / ${ticket.subcategory}` : ''}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">Impact</dt>
                <dd className="font-semibold text-slate-800 capitalize">{ticket.impact}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Urgency</dt>
                <dd className="font-semibold text-slate-800 capitalize">{ticket.urgency}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Assigned group</dt>
                <dd className="font-semibold text-slate-800">{ticket.assigned_group ?? 'Unassigned'}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Created by</dt>
                <dd className="font-semibold text-slate-800">{ticket.created_by ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Created</dt>
                <dd className="font-semibold text-slate-800">{formatDateTime(ticket.created_at)}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Last updated</dt>
                <dd className="font-semibold text-slate-800">{formatDateTime(ticket.updated_at)}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Ticket Age</dt>
                <dd className="font-semibold text-slate-800">{ticket.ticket_age_display || '—'}</dd>
              </div>
              <div className="col-span-2 sm:col-span-1">
                <dt className="text-slate-400">Response SLA</dt>
                <dd className={`font-semibold inline-flex items-center gap-1 ${ticket.response_breached ? 'text-rose-600' : 'text-slate-800'}`}>
                  {ticket.response_breached ? <AlertTriangle className="w-3.5 h-3.5" /> : <Clock className="w-3.5 h-3.5 text-slate-400" />}
                  {formatDateTime(ticket.response_deadline)}
                  {ticket.first_responded_at ? (
                    <span className="text-[10px] text-emerald-600 bg-emerald-50 px-1.5 py-0.2 rounded font-normal">responded</span>
                  ) : ticket.response_breached ? (
                    <span className="text-[10px] text-rose-600 bg-rose-50 px-1.5 py-0.2 rounded font-normal">breached</span>
                  ) : null}
                </dd>
              </div>
              <div className="col-span-2 sm:col-span-1">
                <dt className="text-slate-400">Resolution SLA</dt>
                <dd className={`font-semibold inline-flex items-center gap-1 ${ticket.resolution_breached ? 'text-rose-600' : 'text-slate-800'}`}>
                  {ticket.resolution_breached ? <AlertTriangle className="w-3.5 h-3.5" /> : <Clock className="w-3.5 h-3.5 text-slate-400" />}
                  {formatDateTime(ticket.sla_deadline)}
                  {ticket.resolved_at ? (
                    <span className="text-[10px] text-emerald-600 bg-emerald-50 px-1.5 py-0.2 rounded font-normal">met</span>
                  ) : ticket.is_overdue ? (
                    <span className="text-[10px] text-rose-600 bg-rose-50 px-1.5 py-0.2 rounded font-normal">overdue</span>
                  ) : ticket.resolution_breached ? (
                    <span className="text-[10px] text-rose-600 bg-rose-50 px-1.5 py-0.2 rounded font-normal">breached</span>
                  ) : ticket.is_near_breach ? (
                    <span className="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.2 rounded font-normal">near breach</span>
                  ) : null}
                </dd>
              </div>
            </dl>

            {ticket.resolution_notes && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
                <h3 className="text-xs font-bold text-emerald-800 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Resolution notes
                </h3>
                <p className="text-xs text-emerald-900 mt-1 whitespace-pre-wrap">{ticket.resolution_notes}</p>
                {ticket.resolved_at && (
                  <p className="text-[11px] text-emerald-700 mt-1">Resolved {formatDateTime(ticket.resolved_at)}</p>
                )}
              </div>
            )}

            {!isAdmin && ticket.status === 'resolved' && (
              <button
                onClick={() => setCloseOpen(true)}
                className="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs"
              >
                Confirm resolution &amp; close ticket
              </button>
            )}
          </div>

          {/* AI Escalation & Troubleshooting Handoff (Module 9) */}
          {escalations.length > 0 && (
            <div className="bg-indigo-50/60 rounded-2xl border border-indigo-200 p-6 shadow-xs space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-800 flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-indigo-600" />
                  AI Escalation & Troubleshooting Handoff
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-100 text-indigo-800 border border-indigo-200">
                  Routed to {escalations[0].recommended_group_name}
                </span>
              </div>

              {escalations.map((esc) => (
                <div key={esc.id} className="space-y-3 text-xs text-slate-700 bg-white rounded-xl border border-indigo-100 p-4">
                  <div>
                    <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                      Escalation Summary
                    </div>
                    <p className="text-slate-800 whitespace-pre-wrap">{esc.escalation_summary}</p>
                  </div>

                  {esc.attempted_troubleshooting.length > 0 && (
                    <div>
                      <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        <Wrench className="w-3.5 h-3.5 text-amber-600" /> Attempted Troubleshooting
                      </div>
                      <ul className="list-disc list-inside space-y-0.5 text-slate-700">
                        {esc.attempted_troubleshooting.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {esc.retrieved_references.length > 0 && (
                    <div>
                      <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        <BookOpen className="w-3.5 h-3.5 text-blue-600" /> Knowledge Base References
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {esc.retrieved_references.map((ref, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-[11px] font-medium text-slate-700"
                          >
                            {ref.filename || ref.title || 'KB Source'}
                            {ref.page_number ? ` (p. ${ref.page_number})` : ''}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {esc.relevant_conversation && (
                    <details className="pt-1">
                      <summary className="cursor-pointer text-[11px] font-semibold text-indigo-700 hover:underline">
                        View Relevant Conversation Transcript
                      </summary>
                      <pre className="mt-2 p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-600 whitespace-pre-wrap font-sans">
                        {esc.relevant_conversation}
                      </pre>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Admin edit form */}
          {isAdmin && (
            <form onSubmit={handleSave} className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Update ticket</h2>
              {saveError && (
                <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{saveError}</div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#172B3A] mb-1">Status</label>
                  <AdaptiveSelect
                    label="Status"
                    value={status}
                    onChange={(val) => setStatus(val as StatusValue)}
                    options={STATUS_OPTIONS}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#172B3A] mb-1">Assignment group</label>
                  <AdaptiveSelect
                    label="Assignment group"
                    searchable
                    value={groupId}
                    onChange={(val) => setGroupId(val)}
                    options={[
                      { value: '', label: 'Unassigned' },
                      ...groups.map((g) => ({ value: String(g.id), label: g.name })),
                    ]}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#172B3A] mb-1">Category</label>
                  <AdaptiveSelect
                    label="Category"
                    value={category}
                    onChange={(val) => setCategory(val as TicketCategoryValue)}
                    options={CATEGORY_OPTIONS.map((o) => ({
                      value: o.value,
                      label: o.label,
                      icon: <CategoryIcon category={o.value} className="w-4 h-4 text-[#087E8B]" />,
                    }))}
                  />
                </div>
                <div className="flex items-end">
                  <div className="w-full flex items-center justify-between bg-[#F7F8F6] border border-[#DCE4E3] rounded-xl px-3 py-2">
                    <span className="text-xs text-[#526773]">Priority after save</span>
                    <PriorityBadge priority={previewed} />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#172B3A] mb-1">Impact</label>
                  <AdaptiveSelect
                    label="Impact"
                    value={impact}
                    onChange={(val) => setImpact(val as ImpactLevel)}
                    options={IMPACT_OPTIONS}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#172B3A] mb-1">Urgency</label>
                  <AdaptiveSelect
                    label="Urgency"
                    value={urgency}
                    onChange={(val) => setUrgency(val as UrgencyLevel)}
                    options={URGENCY_OPTIONS}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Resolution notes {(status === 'resolved' || status === 'closed') && <span className="text-rose-600">(required)</span>}
                </label>
                <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} className={inputCls} placeholder="What was done to resolve the issue?" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  AI Recommendation Override Reason <span className="text-slate-400 font-normal">(optional — logs audited AI override)</span>
                </label>
                <input
                  type="text"
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  className={inputCls}
                  placeholder="e.g. Routing to Security Support after manual triage"
                />
              </div>
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] disabled:opacity-60 rounded-lg shadow-xs transition-colors"
                >
                  <Save className="w-4 h-4" />
                  {saving ? 'Saving...' : 'Save changes'}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* History & Relevant Notifications */}
        <div className="space-y-6 h-fit">
          <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs">
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#526773] flex items-center gap-2 mb-4">
              <History className="w-4 h-4 text-[#087E8B]" /> History
            </h2>
            {history.length === 0 ? (
              <p className="text-xs text-[#718096]">No history recorded.</p>
            ) : (
              <ol className="relative border-l border-[#DCE4E3] ml-1.5 space-y-5">
                {[...history].reverse().map((h) => (
                  <li key={h.id} className="ml-4">
                    <span className="absolute -left-1.5 mt-1 w-3 h-3 rounded-full bg-[#087E8B] ring-4 ring-white" />
                    <div className="text-xs font-semibold text-slate-800">
                      {FIELD_LABELS[h.field_changed] ?? h.field_changed}
                    </div>
                    {h.field_changed === 'created' ? (
                      <div className="text-xs text-slate-600">{h.new_value}</div>
                    ) : (
                      <div className="text-xs text-slate-600">
                        <span className="line-through text-slate-400">{prettyValue(h.field_changed, h.old_value)}</span>
                        {' → '}
                        <span className="font-medium">{prettyValue(h.field_changed, h.new_value)}</span>
                      </div>
                    )}
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {h.changed_by ?? 'System'} • {formatDateTime(h.created_at)}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Bell className="w-4 h-4 text-blue-600" /> Relevant Notifications &amp; Email Log
            </h2>
            {ticketNotifications.length === 0 && ticketEmailLogs.length === 0 ? (
              <p className="text-xs text-slate-400">No ticket notifications recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {ticketNotifications.map((n) => (
                  <div
                    key={n.id}
                    className={`rounded-xl border p-3 text-xs ${
                      !n.is_read ? 'bg-blue-50/50 border-blue-200' : 'bg-slate-50 border-slate-200'
                    }`}
                  >
                    <div className="font-semibold text-slate-900">{n.title}</div>
                    <p className="text-[11px] text-slate-600 mt-0.5">{n.message}</p>
                    <div className="text-[10px] text-slate-400 mt-1">{formatDateTime(n.created_at)}</div>
                  </div>
                ))}

                {ticketEmailLogs.length > 0 && (
                  <div className="pt-2 border-t border-slate-100 space-y-2">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                      <Mail className="w-3 h-3 text-slate-400" /> Email Dispatch Audit
                    </div>
                    {ticketEmailLogs.map((log) => (
                      <div key={log.id} className="text-[11px] bg-slate-50 border border-slate-200 rounded-lg p-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-slate-700 truncate">{log.recipient_email}</span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                              log.delivery_status === 'sent'
                                ? 'bg-emerald-100 text-emerald-700'
                                : log.delivery_status === 'failed'
                                ? 'bg-rose-100 text-rose-700'
                                : 'bg-amber-100 text-amber-700'
                            }`}
                          >
                            {log.delivery_status}
                          </span>
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          {log.recipient_verified ? 'Verified email' : 'Unverified address'} • {formatDateTime(log.sent_at || log.created_at)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <ConfirmationDialog
        isOpen={closeOpen}
        onClose={() => setCloseOpen(false)}
        onConfirm={async () => {
          setCloseOpen(false);
          await applyUpdate({ status: 'closed' }, `${ticket.ticket_number} closed.`);
        }}
        title="Close this ticket?"
        message="Confirm the issue is resolved. The ticket will be closed."
        confirmText="Close ticket"
      />
    </div>
  );
};
