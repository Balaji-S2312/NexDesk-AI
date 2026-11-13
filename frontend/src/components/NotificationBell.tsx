import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  Bell,
  CheckCheck,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Ticket as TicketIcon,
  UserCheck,
} from 'lucide-react';
import {
  getUnreadNotificationCountApi,
  listNotificationsApi,
  markAllNotificationsReadApi,
  markNotificationReadApi,
} from '../services/api';
import { NotificationItem } from '../types/notification';

const formatTimeAgo = (iso: string): string => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const diffSec = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (diffSec < 60) return 'Just now';
  const mins = Math.floor(diffSec / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return date.toLocaleDateString();
};

const iconForType = (type: string) => {
  if (type === 'ticket_resolved' || type === 'ticket_resolved_confirmation') {
    return <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />;
  }
  if (type === 'ticket_assigned') {
    return <UserCheck className="w-4 h-4 text-indigo-600 shrink-0" />;
  }
  if (type === 'new_incident_alert') {
    return <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />;
  }
  if (type === 'ticket_status_updated') {
    return <RefreshCw className="w-4 h-4 text-sky-600 shrink-0" />;
  }
  return <TicketIcon className="w-4 h-4 text-blue-600 shrink-0" />;
};

export const NotificationBell: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const containerRef = useRef<HTMLDivElement>(null);

  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);

  const refreshUnread = useCallback(async () => {
    try {
      const res = await getUnreadNotificationCountApi();
      setUnreadCount(res.unread_count);
    } catch {
      // Keep UI resilient if transient network check fails
    }
  }, []);

  const loadDropdown = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listNotificationsApi({ limit: 8 });
      setItems(res.items);
      setUnreadCount(res.unread_count);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUnread();
    const interval = setInterval(refreshUnread, 25_000);
    const onEvent = () => {
      refreshUnread();
      if (open) {
        loadDropdown();
      }
    };
    window.addEventListener('nexdesk-notifications-updated', onEvent);
    return () => {
      clearInterval(interval);
      window.removeEventListener('nexdesk-notifications-updated', onEvent);
    };
  }, [refreshUnread, loadDropdown, open]);

  useEffect(() => {
    refreshUnread();
    setOpen(false);
  }, [location.pathname, refreshUnread]);

  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) {
      document.addEventListener('mousedown', handleOutside);
    }
    return () => document.removeEventListener('mousedown', handleOutside);
  }, [open]);

  const handleToggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      loadDropdown();
    }
  };

  const handleNotificationClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      try {
        await markNotificationReadApi(item.id);
        setItems((prev) => prev.map((x) => (x.id === item.id ? { ...x, is_read: true } : x)));
        setUnreadCount((c) => Math.max(0, c - 1));
        window.dispatchEvent(new Event('nexdesk-notifications-updated'));
      } catch {
        // Proceed with navigation even if mark-read fails
      }
    }
    setOpen(false);
    if (item.link) {
      navigate(item.link);
    } else if (item.ticket_id) {
      navigate(`/tickets/${item.ticket_id}`);
    } else {
      navigate('/notifications');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsReadApi();
      setItems((prev) => prev.map((x) => ({ ...x, is_read: true })));
      setUnreadCount(0);
      window.dispatchEvent(new Event('nexdesk-notifications-updated'));
    } catch {
      // Ignore transient errors
    }
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={handleToggle}
        data-testid="notification-bell"
        aria-label="Open notifications"
        aria-expanded={open}
        className="p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors relative"
        title="Notifications"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span
            data-testid="notification-unread-badge"
            className="absolute -top-0.5 -right-0.5 min-w-[17px] h-[17px] px-1 bg-[#087E8B] text-white text-[10px] font-bold rounded-full flex items-center justify-center ring-2 ring-white"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          data-testid="notification-dropdown"
          className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-2xl border border-[#DCE4E3] shadow-lg overflow-hidden z-50"
        >
          <div className="px-4 py-3 border-b border-[#DCE4E3] flex items-center justify-between bg-[#EFF3F1]/70">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-[#172B3A]">Notifications</span>
              {unreadCount > 0 && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#DCEFF0] text-[#087E8B]">
                  {unreadCount} unread
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#087E8B] hover:text-[#075C66]"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                <span>Mark all read</span>
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto divide-y divide-[#DCE4E3]">
            {loading ? (
              <div className="p-5 text-center text-xs text-[#526773]">Loading notifications...</div>
            ) : items.length === 0 ? (
              <div className="p-6 text-center text-xs text-[#718096]">
                No notifications yet. Ticket events will appear here in real time.
              </div>
            ) : (
              items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleNotificationClick(item)}
                  className={`w-full text-left px-4 py-3 hover:bg-[#EFF3F1] transition-colors flex items-start gap-3 ${
                    !item.is_read ? 'bg-[#DCEFF0]/30' : 'bg-white'
                  }`}
                >
                  <div className="mt-0.5">{iconForType(item.notification_type)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={`text-xs truncate ${
                          !item.is_read ? 'font-bold text-[#172B3A]' : 'font-semibold text-[#526773]'
                        }`}
                      >
                        {item.title}
                      </span>
                      {!item.is_read && (
                        <span className="w-2 h-2 rounded-full bg-[#087E8B] shrink-0" title="Unread" />
                      )}
                    </div>
                    <p className="text-[11px] text-[#526773] mt-0.5 line-clamp-2">{item.message}</p>
                    <div className="flex items-center justify-between mt-1.5 text-[10px] text-[#718096]">
                      <span className="font-mono text-[#718096]">{item.ticket_number || 'System'}</span>
                      <span>{formatTimeAgo(item.created_at)}</span>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-[#DCE4E3] bg-[#EFF3F1]/50 flex items-center justify-between">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                navigate('/notifications');
              }}
              className="w-full py-1.5 text-center text-xs font-semibold text-[#087E8B] hover:text-[#075C66] flex items-center justify-center gap-1"
            >
              <span>View all notifications</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
