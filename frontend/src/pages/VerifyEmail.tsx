import React, { useEffect, useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { CheckCircle2, XCircle, RefreshCw, ArrowRight, Mail, ShieldCheck } from 'lucide-react';
import { verifyEmailWithTokenApi, resendVerificationEmailApi } from '../services/api';
import { useAuth } from '../hooks/useAuth';

export const VerifyEmail: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();
  const { user } = useAuth();

  const [status, setStatus] = useState<'verifying' | 'success' | 'error' | 'idle'>(token ? 'verifying' : 'idle');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [resendEmail, setResendEmail] = useState<string>(user?.email || '');
  const [resendSuccess, setResendSuccess] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (!token) return;

    let mounted = true;
    setStatus('verifying');

    verifyEmailWithTokenApi(token)
      .then(() => {
        if (mounted) {
          setStatus('success');
        }
      })
      .catch((err: unknown) => {
        if (mounted) {
          setStatus('error');
          const msg = err instanceof Error ? err.message : 'Invalid or expired verification token.';
          setErrorMessage(msg);
        }
      });

    return () => {
      mounted = false;
    };
  }, [token]);

  // Cooldown timer for resend
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resendEmail) {
      setErrorMessage('Please enter your registered email address.');
      return;
    }
    setResending(true);
    setResendSuccess(null);
    setErrorMessage('');
    try {
      const res = await resendVerificationEmailApi(resendEmail.trim().toLowerCase());
      setResendSuccess(res.message || 'Verification link sent! Please check your Gmail inbox.');
      setCooldown(60); // 60s cooldown
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to resend verification email.';
      setErrorMessage(msg);
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-app)] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 transition-colors">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-6">
        <div className="inline-flex p-3 bg-[#087E8B] rounded-2xl text-white shadow-md shadow-[#087E8B]/20 mb-3">
          <ShieldCheck className="w-8 h-8" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-[var(--text-primary)] tracking-tight">
          NexDesk AI Email Verification
        </h1>
        <p className="mt-1 text-xs sm:text-sm text-[var(--text-secondary)]">
          Secure Identity Verification & IT Service Notification Registration
        </p>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] py-8 px-6 sm:px-10 shadow-xl rounded-2xl transition-colors">
          {status === 'verifying' && (
            <div className="text-center py-6">
              <RefreshCw className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
              <h2 className="text-lg font-bold text-[var(--text-primary)]">Verifying Your Email...</h2>
              <p className="mt-2 text-xs text-[var(--text-secondary)]">
                Validating cryptographic token with the NexDesk authentication server.
              </p>
            </div>
          )}

          {status === 'success' && (
            <div className="text-center py-4">
              <div className="w-14 h-14 bg-[#EAF5F0] text-[#287A68] rounded-full flex items-center justify-center mx-auto mb-4 border border-[#C3E4D6]">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h2 className="text-xl font-bold text-[var(--text-primary)]">Email Verified Successfully!</h2>
              <p className="mt-2 text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                Your employee email has been confirmed. You now have full authorization to submit IT incidents, access the AI support assistant, and receive real-time email ticket notifications.
              </p>
              <div className="mt-6 space-y-2">
                <button
                  onClick={() => navigate(user ? '/' : '/login')}
                  className="w-full flex items-center justify-center py-2.5 px-4 rounded-xl shadow-xs text-sm font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] transition-colors"
                >
                  <span>{user ? 'Go to Workspace' : 'Continue to Login'}</span>
                  <ArrowRight className="w-4 h-4 ml-2" />
                </button>
              </div>
            </div>
          )}

          {(status === 'error' || status === 'idle') && (
            <div>
              {status === 'error' && (
                <div className="text-center mb-6">
                  <div className="w-14 h-14 bg-rose-50 text-[#C24141] rounded-full flex items-center justify-center mx-auto mb-3 border border-rose-200">
                    <XCircle className="w-8 h-8" />
                  </div>
                  <h2 className="text-lg font-bold text-[var(--text-primary)]">Verification Link Invalid or Expired</h2>
                  <p className="mt-1 text-xs text-[#C24141] font-medium">
                    {errorMessage || 'This verification token is single-use or has exceeded the 30-minute validity deadline.'}
                  </p>
                </div>
              )}

              {status === 'idle' && (
                <div className="text-center mb-6">
                  <div className="w-14 h-14 bg-[#DCEFF0] text-[#087E8B] rounded-full flex items-center justify-center mx-auto mb-3 border border-[#B5E1E4]">
                    <Mail className="w-7 h-7" />
                  </div>
                  <h2 className="text-lg font-bold text-[var(--text-primary)]">Verify Your Employee Account</h2>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    Enter your registered email below to receive a secure activation link.
                  </p>
                </div>
              )}

              {resendSuccess && (
                <div className="mb-4 p-3 rounded-xl bg-[#EAF5F0] border border-[#C3E4D6] text-[#287A68] text-xs flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-[#287A68]" />
                  <span>{resendSuccess}</span>
                </div>
              )}

              <form onSubmit={handleResend} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    Employee Email Address
                  </label>
                  <div className="relative rounded-lg shadow-2xs">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[var(--text-muted)]">
                      <Mail className="w-4 h-4" />
                    </div>
                    <input
                      type="email"
                      required
                      value={resendEmail}
                      onChange={(e) => setResendEmail(e.target.value)}
                      placeholder="employee@nexdesk.ai"
                      className="block w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-input)] text-[var(--text-input)] placeholder-[var(--placeholder)] focus:ring-2 focus:ring-[#087E8B]"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={resending || cooldown > 0}
                  className="w-full flex justify-center items-center py-2.5 px-4 border border-transparent rounded-xl shadow-xs text-xs font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {resending ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 mr-2 animate-spin" />
                      Sending Verification Email...
                    </>
                  ) : cooldown > 0 ? (
                    `Resend Available in ${cooldown}s`
                  ) : (
                    'Send Verification Link'
                  )}
                </button>
              </form>

              <div className="mt-6 pt-4 border-t border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
                Already verified?{' '}
                <Link to="/login" className="font-semibold text-[#087E8B] hover:text-[#075C66]">
                  Sign In
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
