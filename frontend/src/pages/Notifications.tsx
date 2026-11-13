import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  Bell,
  CheckCheck,
  CheckCircle2,
  ExternalLink,
  Mail,
  RefreshCw,
  ShieldAlert,
  Ticket as TicketIcon,
  UserCheck,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import {
  getNotificationConfigApi,
  listEmailHistoryApi,
  listNotificationsApi,
  markAllNotificationsReadApi,
  markNotificationReadApi,
} from '../services/api';
import {
  EmailDeliveryLogItem,
  NotificationConfigStatus,
  NotificationItem,
} from '../types/notification';
import { formatDateTime } from '../utils/ticketOptions';

const deliveryBadgeCls = (status: string) => {
  if (status === 'sent') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (status === 'failed') return 'bg-rose-50 text-rose-700 border-rose-200';
  return 'bg-amber-50 text-amber-700 border-amber-200';
};

const iconForType = (type: string) => {
  if (type === 'ticket_resolved' || type === 'ticket_resolved_confirmation' || type === 'ticket_closed') {
    return <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />;
  }
  if (type === 'ticket_assigned') {
    return <UserCheck className="w-4 h-4 text-indigo-600 shrink-0" />;
  }
  if (
    type === 'new_incident_alert' ||
    type === 'high_priority_alert' ||
    type === 'ticket_escalated' ||
    type === 'sla_breached' ||
    type === 'sla_approaching'
  ) {
    return <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />;
  }
  if (
    type === 'ticket_status_updated' ||
    type === 'ticket_priority_updated' ||
    type === 'admin_comment' ||
    type === 'employee_reply'
  ) {
    return <RefreshCw className="w-4 h-4 text-sky-600 shrink-0" />;
  }
  return <TicketIcon className="w-4 h-4 text-blue-600 shrink-0" />;
};

export const Notifications: React.FC = () => {
  const navigate = useNavigate();
  const { user, isAdmin } = useAuth();
  const { showToast } = useToast();

  const [tab, setTab] = useState<'in_app' | 'email_logs'>('in_app');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [emailLogs, setEmailLogs] = useState<EmailDeliveryLogItem[]>([]);
  const [configStatus, setConfigStatus] = useState<NotificationConfigStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [notifRes, emailRes, cfgRes] = await Promise.all([
        listNotificationsApi({ unread_only: unreadOnly, limit: 100 }),
        listEmailHistoryApi({ limit: 100 }),
        isAdmin ? getNotificationConfigApi().catch(() => null) : Promise.resolve(null),
      ]);
      setNotifications(notifRes.items);
      setUnreadCount(notifRes.unread_count);
      setEmailLogs(emailRes);
      setConfigStatus(cfgRes);
    } catch (err: unknown) {
      if (!silent) {
        showToast({
          type: 'error',
          title: 'Notification load failed',
          message: err instanceof Error ? err.message : 'Unable to fetch notifications',
        });
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [unreadOnly, isAdmin, showToast]);

  useEffect(() => {
    loadAll(false);
    const interval = setInterval(() => loadAll(true), 15_000);
    const onUpdated = () => loadAll(true);
    window.addEventListener('nexdesk-notifications-updated', onUpdated);
    return () => {
      clearInterval(interval);
      window.removeEventListener('nexdesk-notifications-updated', onUpdated);
    };
  }, [loadAll]);

  const handleMarkRead = async (item: NotificationItem) => {
    try {
      const updated = await markNotificationReadApi(item.id);
      setNotifications((prev) =>
        prev
          .map((n) => (n.id === item.id ? updated : n))
          .filter((n) => (unreadOnly ? !n.is_read : true))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
      window.dispatchEvent(new Event('nexdesk-notifications-updated'));
    } catch (err: unknown) {
      showToast({
        type: 'error',
        title: 'Action failed',
        message: err instanceof Error ? err.message : 'Unable to mark notification read',
      });
    }
  };

  const handleMarkAllRead = async () => {
    try {
      const res = await markAllNotificationsReadApi();
      setNotifications((prev) =>
        unreadOnly ? [] : prev.map((n) => ({ ...n, is_read: true }))
      );
      setUnreadCount(0);
      window.dispatchEvent(new Event('nexdesk-notifications-updated'));
      showToast({
        type: 'success',
        title: 'All notifications read',
        message: `Marked ${res.marked_count} notification(s) as read.`,
      });
    } catch (err: unknown) {
      showToast({
        type: 'error',
        title: 'Action failed',
        message: err instanceof Error ? err.message : 'Unable to mark all as read',
      });
    }
  };

  const handleOpenTicket = async (item: NotificationItem) => {
    if (!item.is_read) {
      await handleMarkRead(item);
    }
    if (item.link) navigate(item.link);
    else if (item.ticket_id) navigate(`/tickets/${item.ticket_id}`);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-[#087E8B] uppercase tracking-wider mb-1">
            <Bell className="w-3.5 h-3.5" />
            <span>Notification Centre</span>
          </div>
          <h1 className="text-2xl font-bold text-[#172B3A] tracking-tight">
            Notifications &amp; Email History
          </h1>
          <p className="text-xs text-[#526773] mt-1">
            Real-time ticket submissions, assignments, status transitions, resolutions, and delivery logs.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => loadAll(false)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white hover:bg-[#EFF3F1] text-[#172B3A] border border-[#DCE4E3] text-xs font-semibold shadow-2xs transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#087E8B]' : 'text-[#718096]'}`} />
            <span>Refresh</span>
          </button>
          {unreadCount > 0 && (
            <button
              type="button"
              onClick={handleMarkAllRead}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#087E8B] hover:bg-[#075C66] text-white text-xs font-semibold shadow-xs transition-colors"
            >
              <CheckCheck className="w-4 h-4" />
              <span>Mark All Read ({unreadCount})</span>
            </button>
          )}
        </div>
      </div>

      {/* Verification Status / Admin Email Routing Banner */}
      {!isAdmin && user && !user.email_verified && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-bold text-amber-900">
                Registered Email Status: Unconfirmed ({user.email})
              </div>
              <p className="text-xs text-amber-800 mt-0.5">
                Notifications route to your registered email address. You can mark your address as User-confirmed on your profile page.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate('/profile')}
            className="px-3.5 py-1.5 rounded-lg bg-[#087E8B] hover:bg-[#075C66] text-white text-xs font-semibold shrink-0 transition-colors cursor-pointer"
          >
            Confirm in Profile
          </button>
        </div>
      )}

      {isAdmin && configStatus && (
        <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2.5">
            <Mail className="w-4 h-4 text-blue-600 shrink-0" />
            <div>
              <span className="font-bold text-slate-900">Admin Incident Alert Email:</span>{' '}
              <span className="font-mono text-slate-700">{configStatus.admin_notification_email}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${
                configStatus.https_provider_configured
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : configStatus.smtp_configured
                  ? 'bg-sky-50 text-sky-700 border-sky-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
            >
              {configStatus.https_provider_configured
                ? 'HTTPS Email API Ready (Port 443)'
                : configStatus.smtp_configured
                ? `SMTP Configured (${configStatus.smtp_host}:${configStatus.smtp_port} — In-App Always Active)`
                : 'Email Not Configured — In-App Active'}
            </span>
          </div>
        </div>
      )}

      {/* Tabs & Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#DCE4E3] pb-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setTab('in_app')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              tab === 'in_app'
                ? 'bg-[#087E8B] text-white shadow-2xs'
                : 'bg-white text-[#526773] border border-[#DCE4E3] hover:bg-[#EFF3F1]'
            }`}
          >
            In-App Notifications ({notifications.length})
          </button>
          <button
            type="button"
            onClick={() => setTab('email_logs')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              tab === 'email_logs'
                ? 'bg-[#087E8B] text-white shadow-2xs'
                : 'bg-white text-[#526773] border border-[#DCE4E3] hover:bg-[#EFF3F1]'
            }`}
          >
            Email Delivery Logs ({emailLogs.length})
          </button>
        </div>

        {tab === 'in_app' && (
          <div className="flex items-center gap-1.5 text-xs">
            <button
              type="button"
              onClick={() => setUnreadOnly(false)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                !unreadOnly ? 'bg-[#172B3A] text-white' : 'bg-white text-[#526773] border border-[#DCE4E3]'
              }`}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setUnreadOnly(true)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                unreadOnly ? 'bg-[#172B3A] text-white' : 'bg-white text-[#526773] border border-[#DCE4E3]'
              }`}
            >
              Unread Only
            </button>
          </div>
        )}
      </div>

      {tab === 'in_app' ? (
        <div className="space-y-3">
          {loading ? (
            <div className="bg-white border border-[#DCE4E3] rounded-2xl p-8 text-center text-xs text-[#526773]">
              Loading notifications...
            </div>
          ) : notifications.length === 0 ? (
            <div className="bg-white border border-[#DCE4E3] rounded-2xl p-10 text-center text-xs text-[#718096]">
              {unreadOnly ? 'No unread notifications.' : 'No notifications recorded yet.'}
            </div>
          ) : (
            notifications.map((item) => (
              <div
                key={item.id}
                className={`rounded-2xl border p-4 shadow-2xs transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                  !item.is_read
                    ? 'bg-[#DCEFF0]/40 border-[#B5E1E4]'
                    : 'bg-white border-[#DCE4E3]'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-xl bg-white border border-[#DCE4E3] shadow-2xs">
                    {iconForType(item.notification_type)}
                  </div>
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-bold text-[#172B3A]">{item.title}</span>
                      {!item.is_read && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#087E8B] text-white uppercase">
                          Unread
                        </span>
                      )}
                      {item.ticket_number && (
                        <span className="px-2 py-0.5 rounded bg-[#EFF3F1] text-[#172B3A] font-mono text-[11px] font-semibold">
                          {item.ticket_number}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#172B3A] leading-relaxed">{item.message}</p>
                    <div className="text-[11px] text-[#718096]">
                      {formatDateTime(item.created_at)}
                      {item.read_at ? ` • Read ${formatDateTime(item.read_at)}` : ''}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {!item.is_read && (
                    <button
                      type="button"
                      onClick={() => handleMarkRead(item)}
                      className="px-3 py-1.5 rounded-lg border border-[#DCE4E3] bg-white hover:bg-[#EFF3F1] text-xs font-semibold text-[#172B3A] transition-colors"
                    >
                      Mark Read
                    </button>
                  )}
                  {(item.ticket_id || item.link) && (
                    <button
                      type="button"
                      onClick={() => handleOpenTicket(item)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#087E8B] hover:bg-[#075C66] text-white text-xs font-semibold shadow-2xs transition-colors"
                    >
                      <span>View Ticket</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-[#DCE4E3] shadow-xs overflow-hidden">
          {emailLogs.length === 0 ? (
            <div className="p-10 text-center text-xs text-slate-400">
              No outbound email delivery logs recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider">
                  <tr>
                    <th className="px-4 py-3 text-left">Ticket</th>
                    <th className="px-4 py-3 text-left">Recipient</th>
                    <th className="px-4 py-3 text-left">Subject</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-left">Details</th>
                    <th className="px-4 py-3 text-left">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {emailLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-3 font-mono font-semibold text-slate-700">
                        {log.ticket_number || '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-800">{log.recipient_email}</div>
                        <div className="text-[10px] text-slate-400">
                          {log.recipient_verified ? 'Verified' : 'Unverified address'} • {log.event_type}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-800">{log.subject}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold border ${deliveryBadgeCls(
                            log.delivery_status
                          )}`}
                        >
                          {log.delivery_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-500 max-w-xs truncate" title={log.error_message || ''}>
                        {log.error_message || `${log.attempt_count} attempt(s)`}
                      </td>
                      <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                        {formatDateTime(log.sent_at || log.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
