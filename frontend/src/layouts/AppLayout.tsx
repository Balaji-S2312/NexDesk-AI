import { useState, useCallback, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { TopNavbar } from '../components/TopNavbar';
import { getHealthApi } from '../services/api';
import { HealthResponse } from '../types/api';

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/ai-support': 'AI Support Assistant',
  '/ai-assistant': 'AI Assistant',
  '/my-tickets': 'My Tickets',
  '/notifications': 'Notification Centre',
  '/knowledge-base': 'Knowledge Base',
  '/profile': 'My Profile',
  '/incidents': 'All Incidents',
  '/assignment-groups': 'Assignment Groups',
  '/sla-management': 'SLA Management',
  '/audit-logs': 'Audit Logs',
  '/settings': 'System Settings',
};

export const AppLayout = () => {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const data = await getHealthApi();
      setHealth(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Backend unreachable';
      setHealthError(msg);
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    // Ping health every 60 seconds
    const interval = setInterval(fetchHealth, 60_000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const pageTitle = location.pathname.startsWith('/tickets/')
    ? 'Ticket Details'
    : PAGE_TITLES[location.pathname] ?? 'NexDesk AI';

  return (
    <div className="min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)] flex transition-colors">
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopNavbar
          onOpenMobileSidebar={() => setMobileOpen(true)}
          health={health}
          healthLoading={healthLoading}
          healthError={healthError}
          onRefreshHealth={fetchHealth}
          pageTitle={pageTitle}
        />

        <main className="flex-1 overflow-y-auto p-5 sm:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
