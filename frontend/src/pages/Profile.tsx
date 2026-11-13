import React, { useState } from 'react';
import {
  User,
  Key,
  Calendar,
  LogOut,
  CheckCircle2,
  Mail,
  ShieldAlert,
  AlertCircle,
  BadgeCheck,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { confirmEmailApi } from '../services/api';
import { Modal } from '../components/Modal';

export const Profile: React.FC = () => {
  const { user, isAdmin, logout, refreshUser } = useAuth();
  const { showToast } = useToast();

  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [confirmEmailInput, setConfirmEmailInput] = useState('');
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [confirmSuccessMessage, setConfirmSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const openConfirmModal = () => {
    setConfirmEmailInput('');
    setConfirmError(null);
    setIsConfirmModalOpen(true);
  };

  const closeConfirmModal = () => {
    if (submitting) return;
    setIsConfirmModalOpen(false);
    setConfirmError(null);
  };

  const handleConfirmSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || submitting) return;

    const trimmed = confirmEmailInput.trim();
    if (!trimmed) {
      setConfirmError('Please re-enter your registered email address.');
      return;
    }

    setSubmitting(true);
    setConfirmError(null);
    try {
      const res = await confirmEmailApi(confirmEmailInput);
      if (refreshUser) {
        await refreshUser();
      }
      setConfirmSuccessMessage(res.message || 'Email address confirmed successfully.');
      setIsConfirmModalOpen(false);
      setConfirmEmailInput('');
      showToast({
        type: 'success',
        title: 'Email Confirmed',
        message: res.message || 'Email address confirmed successfully.',
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error && err.message
          ? err.message
          : 'The email addresses do not match. Please check and try again.';
      setConfirmError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const isConfirmed = Boolean(user?.email_verified);

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

      {/* Email Confirmation Section */}
      <div className="bg-white rounded-xl border border-[#DCE4E3] p-5 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-[#DCE4E3]">
          <div className="flex items-center space-x-2 text-xs font-bold text-[#172B3A] uppercase tracking-wider">
            <Mail className="w-4 h-4 text-[#087E8B]" />
            <span>Email Confirmation</span>
          </div>
          {isConfirmed ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#EAF5F0] text-[#287A68] border border-[#C3E4D6] w-fit">
              <BadgeCheck className="w-3.5 h-3.5" />
              User-confirmed
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200 w-fit">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
              Unconfirmed
            </span>
          )}
        </div>

        {confirmSuccessMessage && (
          <div
            role="status"
            className="flex items-center gap-2 rounded-lg bg-[#EAF5F0] border border-[#C3E4D6] px-3.5 py-2.5 text-xs font-semibold text-[#287A68]"
          >
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{confirmSuccessMessage}</span>
          </div>
        )}

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 text-xs">
          <div className="space-y-1.5">
            <div>
              <span className="text-[#718096] block text-[11px]">Registered Email Address</span>
              <span className="font-semibold text-[#172B3A] font-mono">{user?.email}</span>
            </div>
            <div>
              <span className="text-[#718096] block text-[11px]">Confirmation Status</span>
              <span className="font-semibold text-[#172B3A]">
                {isConfirmed ? 'User-confirmed' : 'Unconfirmed'}
              </span>
              {isConfirmed && user?.email_verified_at && (
                <span className="text-[#718096] ml-2">
                  ({new Date(user.email_verified_at).toLocaleString()})
                </span>
              )}
            </div>
            <p className="text-[11px] text-[#526773] pt-0.5">
              In-app user confirmation records that you re-entered your registered email address here. It does not constitute proof of external mailbox ownership.
            </p>
          </div>

          {!isConfirmed && (
            <button
              type="button"
              onClick={openConfirmModal}
              className="px-4 py-2 rounded-lg bg-[#087E8B] hover:bg-[#075C66] text-white text-xs font-semibold shadow-xs transition-colors shrink-0 cursor-pointer"
            >
              Confirm Email
            </button>
          )}
        </div>
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
                {isConfirmed ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#EAF5F0] text-[#287A68] border border-[#C3E4D6]">
                    <Mail className="w-3 h-3" /> User-confirmed
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                    <ShieldAlert className="w-3 h-3" /> Unconfirmed
                  </span>
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

      {/* Confirm Email Modal */}
      <Modal
        isOpen={isConfirmModalOpen}
        onClose={closeConfirmModal}
        title="Confirm Your Email Address"
        description="Re-enter your registered email address below to mark it as User-confirmed on your profile."
        maxWidth="md"
        footer={
          <>
            <button
              type="button"
              onClick={closeConfirmModal}
              disabled={submitting}
              className="px-3.5 py-2 text-xs font-semibold text-[#526773] bg-white border border-[#DCE4E3] hover:bg-[#F7F9F9] rounded-lg disabled:opacity-60 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="confirm-email-form"
              disabled={submitting}
              className="px-4 py-2 text-xs font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] disabled:opacity-60 rounded-lg shadow-xs cursor-pointer"
            >
              {submitting ? 'Confirming...' : 'Confirm Email'}
            </button>
          </>
        }
      >
        <form id="confirm-email-form" onSubmit={handleConfirmSubmit} className="space-y-4">
          <div className="rounded-lg bg-[#F7F9F9] border border-[#DCE4E3] p-3">
            <span className="text-[11px] text-[#718096] block">Registered Email Address</span>
            <span className="text-xs font-semibold text-[#172B3A] font-mono break-all">
              {user?.email}
            </span>
          </div>

          {confirmError && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg bg-rose-50 border border-rose-200 px-3 py-2.5 text-xs text-rose-700 font-medium"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
              <span>{confirmError}</span>
            </div>
          )}

          <div>
            <label
              htmlFor="confirm-email-input"
              className="block text-xs font-semibold text-[#172B3A] mb-1.5"
            >
              Re-enter Email Address
            </label>
            <input
              id="confirm-email-input"
              type="email"
              required
              autoFocus
              value={confirmEmailInput}
              onChange={(e) => {
                setConfirmEmailInput(e.target.value);
                if (confirmError) setConfirmError(null);
              }}
              placeholder="Re-enter your registered email address"
              className="w-full px-3 py-2 text-xs bg-white border border-[#DCE4E3] rounded-lg text-[#172B3A] focus:outline-none focus:ring-2 focus:ring-[#087E8B]/20 focus:border-[#087E8B]"
            />
          </div>

          <p className="text-[11px] text-[#718096] leading-relaxed">
            Matching ignores leading/trailing spaces and letter casing. This self-service check updates your profile status to User-confirmed and does not validate external inbox ownership.
          </p>
        </form>
      </Modal>
    </div>
  );
};
