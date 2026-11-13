import React from 'react';
import { Menu, Shield, User as UserIcon } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { HealthBadge } from './HealthBadge';
import { NotificationBell } from './NotificationBell';
import { HealthResponse } from '../types/api';

interface TopNavbarProps {
  onOpenMobileSidebar: () => void;
  health: HealthResponse | null;
  healthLoading: boolean;
  healthError: string | null;
  onRefreshHealth: () => void;
  pageTitle?: string;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({
  onOpenMobileSidebar,
  health,
  healthLoading,
  healthError,
  onRefreshHealth,
  pageTitle,
}) => {
  const { user, isAdmin } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-[#DCE4E3] px-4 sm:px-8 flex items-center justify-between sticky top-0 z-30 shadow-xs">
      <div className="flex items-center space-x-3">
        {/* Mobile menu trigger */}
        <button
          onClick={onOpenMobileSidebar}
          className="md:hidden p-2 rounded-lg text-[#526773] hover:text-[#172B3A] hover:bg-[#EFF3F1] transition-colors"
          title="Open menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Page Title & Breadcrumbs */}
        <div>
          <h2 className="text-base font-bold text-[#172B3A] leading-tight">
            {pageTitle || (isAdmin ? 'Admin Dashboard' : 'Employee Workspace')}
          </h2>
          <div className="text-[11px] text-[#526773] hidden sm:block">
            NexDesk ITSM Platform &bull; {isAdmin ? 'Enterprise Operations' : 'Self-Service Portal'}
          </div>
        </div>
      </div>

      {/* Right controls */}
      <div className="flex items-center space-x-3 sm:space-x-4">
        {/* Backend health status badge */}
        <HealthBadge
          health={health}
          loading={healthLoading}
          error={healthError}
          onRefresh={onRefreshHealth}
        />

        {/* Notifications Bell & Dropdown */}
        <NotificationBell />

        {/* User Mini Avatar */}
        <div className="flex items-center space-x-2 pl-3 border-l border-[#DCE4E3]">
          <div className="w-8 h-8 rounded-full bg-[#DCEFF0] border border-[#B5E1E4] flex items-center justify-center font-bold text-xs text-[#087E8B]">
            {isAdmin ? <Shield className="w-4 h-4 text-[#087E8B]" /> : <UserIcon className="w-4 h-4 text-[#087E8B]" />}
          </div>
          <span className="text-xs font-semibold text-[#172B3A] hidden lg:inline">
            {user?.name}
          </span>
        </div>
      </div>
    </header>
  );
};
