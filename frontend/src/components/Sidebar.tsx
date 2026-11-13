import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import {
  Cpu,
  LayoutDashboard,
  Bot,
  LifeBuoy,
  BookOpen,
  User as UserIcon,
  Users,
  Clock,
  ShieldCheck,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Flame,
  Bell,
} from 'lucide-react';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}) => {
  const { user, isAdmin, logout } = useAuth();

  // Navigation Items according to specifications
  const employeeNav = [
    { name: 'Overview', to: '/', icon: LayoutDashboard },
    { name: 'AI Support', to: '/ai-support', icon: Bot },
    { name: 'My Tickets', to: '/my-tickets', icon: LifeBuoy },
    { name: 'Notifications', to: '/notifications', icon: Bell },
    { name: 'Knowledge Base', to: '/knowledge-base', icon: BookOpen },
    { name: 'Profile', to: '/profile', icon: UserIcon },
  ];

  const adminNav = [
    { name: 'Dashboard', to: '/', icon: LayoutDashboard },
    { name: 'Incidents', to: '/incidents', icon: Flame },
    { name: 'Notifications', to: '/notifications', icon: Bell },
    { name: 'AI Assistant', to: '/ai-assistant', icon: Bot },
    { name: 'Knowledge Base', to: '/knowledge-base', icon: BookOpen },
    { name: 'Assignment Groups', to: '/assignment-groups', icon: Users },
    { name: 'SLA Management', to: '/sla-management', icon: Clock },
    { name: 'Audit Logs', to: '/audit-logs', icon: ShieldCheck },
    { name: 'Settings', to: '/settings', icon: Settings },
  ];

  const navItems = isAdmin ? adminNav : employeeNav;

  const sidebarContent = (
    <div className="flex flex-col h-full bg-[#FFFFFF] border-r border-[#DCE4E3] select-none">
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-[#DCE4E3]">
        <div className="flex items-center space-x-3 overflow-hidden">
          <div className="p-2 bg-[#087E8B] rounded-xl text-white shadow-xs shrink-0">
            <Cpu className="w-5 h-5" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <h1 className="font-bold text-base text-[#172B3A] tracking-tight leading-none">NexDesk AI</h1>
              <span className="text-[10px] font-semibold text-[#087E8B] uppercase tracking-wider">Enterprise ITSM</span>
            </div>
          )}
        </div>

        {/* Desktop Collapse Toggle */}
        <button
          onClick={onToggleCollapse}
          className="hidden md:flex p-1.5 rounded-lg text-[#526773] hover:text-[#172B3A] hover:bg-[#EFF3F1] transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {!collapsed && (
          <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-[#526773]">
            {isAdmin ? 'Administration' : 'Service Workspace'}
          </div>
        )}

        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.name}
              to={item.to}
              onClick={onCloseMobile}
              className={({ isActive }) =>
                `flex items-center rounded-xl font-medium text-xs transition-colors ${
                  collapsed ? 'justify-center p-2.5' : 'px-3 py-2.5 space-x-3'
                } ${
                  isActive
                    ? 'bg-[#DCEFF0] text-[#087E8B] font-semibold border-r-4 border-[#087E8B]'
                    : 'text-[#172B3A] hover:bg-[#EFF3F1] hover:text-[#087E8B]'
                }`
              }
              title={collapsed ? item.name : undefined}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {!collapsed && <span className="truncate">{item.name}</span>}
            </NavLink>
          );
        })}
      </div>

      {/* User Footer Profile & Sign Out */}
      <div className="p-3 border-t border-[#DCE4E3] bg-[#EFF3F1]">
        {!collapsed && user && (
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="flex items-center space-x-2.5 min-w-0 pr-2">
              <div className="w-8 h-8 rounded-full bg-[#DCEFF0] border border-[#B5E1E4] flex items-center justify-center font-bold text-xs text-[#087E8B] uppercase shrink-0">
                {user.name.charAt(0)}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-[#172B3A] truncate">{user.name}</div>
                <div className="text-[10px] text-[#526773] truncate">{user.email}</div>
              </div>
            </div>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase shrink-0 ${
                isAdmin
                  ? 'bg-purple-100 text-purple-700 border border-purple-200'
                  : 'bg-[#DCEFF0] text-[#087E8B] border border-[#B5E1E4]'
              }`}
            >
              {user.role}
            </span>
          </div>
        )}

        <button
          onClick={logout}
          className={`w-full flex items-center rounded-xl text-xs font-semibold text-[#526773] hover:text-[#C24141] hover:bg-rose-50 transition-colors ${
            collapsed ? 'justify-center p-2.5' : 'px-3 py-2 space-x-2.5'
          }`}
          title="Sign out of your session"
        >
          <LogOut className="w-4 h-4 shrink-0 text-[#718096] hover:text-[#C24141]" />
          {!collapsed && <span>Sign Out</span>}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-xs md:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Mobile Offcanvas Drawer */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 ease-in-out md:hidden ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ display: mobileOpen ? 'block' : 'none' }}
      >
        {sidebarContent}
      </div>

      {/* Desktop Persistent Sidebar */}
      <aside
        className={`hidden md:block shrink-0 transition-all duration-300 ease-in-out ${
          collapsed ? 'w-16' : 'w-64'
        }`}
      >
        <div className={`fixed inset-y-0 left-0 z-20 ${collapsed ? 'w-16' : 'w-64'} transition-all duration-300`}>
          {sidebarContent}
        </div>
      </aside>
    </>
  );
};
