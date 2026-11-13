import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { verifyUserEmailApi } from '../services/api';
import { User, Key, Calendar, LogOut, CheckCircle2, Mail, ShieldAlert } from 'lucide-react';

export const Profile: React.FC = () => {
  const { user, isAdmin, logout, refreshUser } = useAuth();
  const { showToast } = useToast();
  const [verifying, setVerifying] = useState(false);

  const handleVerifyEmail = async () => {
    setVerifying(true);
    try {
      await verifyUserEmailApi();
      if (refreshUser) await refreshUser();
      showToast({
        type: 'success',
        title: 'Email verified',
        message: 'Your email address is now marked as verified for ticket notifications.',
      });
    } catch (err: unknown) {
      showToast({
        type: 'error',
        title: 'Verification failed',
        message: err instanceof Error ? err.message : 'Unable to verify email',
      });
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="w-14 h-14 rounded-2xl bg-[#DCEFF0] border border-[#B5E1E4] flex items-center justify-center font-bold text-xl text-[#087E8B]">
            {user?.name?.charAt(0) || 'U'}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-[#172B3A]">{user?.name}</h1>
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                  isAdmin
                    ? 'bg-purple-100 text-purple-700 border border-purple-200'
                    : 'bg-[#DCEFF0] text-[#087E8B] border border-[#B5E1E4]'
                }`}
              >
                {user?.role.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-[#526773] mt-0.5">{user?.email}</p>
          </div>
        </div>

        <button
          onClick={logout}
          className="flex items-center space-x-1.5 px-3.5 py-2 border border-[#DCE4E3] hover:border-rose-300 text-[#172B3A] hover:text-[#C24141] rounded-lg text-xs font-semibold hover:bg-rose-50 transition-colors shadow-2xs"
        >
          <LogOut className="w-4 h-4" />
          <span>Sign Out</span>
        </button>
      </div>

      {/* Account Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="bg-white rounded-xl border border-[#DCE4E3] p-5 shadow-xs space-y-4">
          <div className="flex items-center space-x-2 text-xs font-bold text-[#172B3A] uppercase tracking-wider pb-2 border-b border-[#DCE4E3]">
            <User className="w-4 h-4 text-[#087E8B]" />
            <span>Profile Identity</span>
          </div>
          <div className="space-y-3 text-xs">
            <div>
              <span className="text-[#718096] block text-[11px]">Full Name</span>
              <span className="font-semibold text-[#172B3A]">{user?.name}</span>
            </div>
            <div>
              <span className="text-[#718096] block text-[11px]">Enterprise Email</span>
              <div className="flex flex-wrap items-center gap-2 mt-0.5">
                <span className="font-semibold text-[#172B3A] font-mono">{user?.email}</span>
                {user?.email_verified ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#EAF5F0] text-[#287A68] border border-[#C3E4D6]">
                    <Mail className="w-3 h-3" /> Verified
                  </span>
                ) : (
                  <>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                      <ShieldAlert className="w-3 h-3" /> Unverified
                    </span>
                    <button
                      type="button"
                      onClick={handleVerifyEmail}
                      disabled={verifying}
                      className="px-2 py-0.5 rounded-md bg-[#087E8B] hover:bg-[#075C66] text-white text-[10px] font-semibold disabled:opacity-60 transition-colors"
                    >
                      {verifying ? 'Verifying...' : 'Verify Email'}
                    </button>
                  </>
                )}
              </div>
            </div>
            <div>
              <span className="text-[#718096] block text-[11px]">Account ID</span>
              <span className="font-semibold text-[#172B3A] font-mono">USER-00{user?.id}</span>
            </div>
            <div>
              <span className="text-[#718096] block text-[11px]">Provisioned At</span>
              <div className="flex items-center space-x-1.5 text-[#526773] mt-0.5">
                <Calendar className="w-3.5 h-3.5 text-[#718096]" />
                <span>{user?.created_at ? new Date(user.created_at).toLocaleString() : 'Active session'}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#DCE4E3] p-5 shadow-xs space-y-4">
          <div className="flex items-center space-x-2 text-xs font-bold text-[#172B3A] uppercase tracking-wider pb-2 border-b border-[#DCE4E3]">
            <Key className="w-4 h-4 text-[#087E8B]" />
            <span>Security & Session Credentials</span>
          </div>
          <div className="space-y-3 text-xs">
            <div>
              <span className="text-[#718096] block text-[11px]">Authentication Mechanism</span>
              <span className="font-semibold text-[#172B3A]">Signed JSON Web Token (HS256)</span>
            </div>
            <div>
              <span className="text-[#718096] block text-[11px]">Password Encryption</span>
              <span className="font-semibold text-[#172B3A]">Bcrypt Salted Hash (Never stored plaintext)</span>
            </div>
            <div>
              <span className="text-[#718096] block text-[11px]">Access Scope</span>
              <span className="font-semibold text-[#172B3A]">
                {isAdmin ? 'Full Tenant Administration' : 'Scoped to Personal Tickets & Profile'}
              </span>
            </div>
            <div className="pt-2 border-t border-[#DCE4E3] flex items-center space-x-1.5 text-[#287A68]">
              <CheckCircle2 className="w-4 h-4 text-[#287A68] shrink-0" />
              <span className="font-medium text-[11px]">Session verified by FastAPI backend gateway</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
