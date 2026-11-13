import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import {
  Cpu,
  Lock,
  Mail,
  User as UserIcon,
  AlertCircle,
  ArrowRight,
  Shield,
  CheckCircle2,
  ShieldCheck,
  Loader2,
} from 'lucide-react';

export const PENDING_VERIFY_EMAIL_KEY = 'nexdesk_pending_verify_email';

export const Register: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [duplicateAccount, setDuplicateAccount] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null);
  const [deliveryStatus, setDeliveryStatus] = useState<string | null>(null);
  const [deliveryError, setDeliveryError] = useState<string | null>(null);

  const { register, clearError } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;

    setLocalError(null);
    setDuplicateAccount(false);
    clearError();

    const trimmedName = name.trim();
    const normalizedEmail = email.trim().toLowerCase();

    if (!trimmedName || !normalizedEmail || !password) {
      setLocalError('All fields are required.');
      return;
    }

    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters long.');
      return;
    }

    setSubmitting(true);
    try {
      const created = await register({
        name: trimmedName,
        email: normalizedEmail,
        password,
      });
      const finalEmail = created.email || normalizedEmail;
      try {
        sessionStorage.setItem(PENDING_VERIFY_EMAIL_KEY, finalEmail);
      } catch {
        // Ignore storage restrictions
      }
      setDeliveryStatus(created.verification_delivery_status || null);
      setDeliveryError(created.verification_delivery_error || null);
      setRegisteredEmail(finalEmail);
    } catch (err: unknown) {
      const apiErr = err as Error & { status?: number };
      const msg = apiErr instanceof Error ? apiErr.message : '';
      const isDuplicate =
        apiErr?.status === 409 ||
        msg.toLowerCase().includes('already exists') ||
        msg.toLowerCase().includes('already registered');

      if (isDuplicate) {
        setDuplicateAccount(true);
        setLocalError(
          'This email address is already registered. Please go to the Login page and sign in using your existing credentials.'
        );
      } else if (msg && !msg.toLowerCase().includes('integrity') && !msg.toLowerCase().includes('unique constraint')) {
        setLocalError(msg);
      } else {
        setLocalError('Registration failed. Please check your details and try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F8F6] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center px-4">
        <div className="inline-flex p-3 bg-[#087E8B] rounded-2xl text-white shadow-md shadow-[#087E8B]/20 mb-4">
          <Cpu className="w-8 h-8" />
        </div>
        <h2 className="text-3xl font-extrabold text-[#172B3A] tracking-tight">
          {registeredEmail ? 'Account Created' : 'Create Account'}
        </h2>
        <p className="mt-1 text-sm text-[#526773]">
          {registeredEmail ? 'NexDesk AI Employee Onboarding' : 'Join the NexDesk AI enterprise support platform'}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-sm rounded-2xl sm:px-10 border border-[#DCE4E3]">
          {registeredEmail ? (
            <div className="space-y-5 text-center">
              <div className="w-14 h-14 mx-auto rounded-full bg-[#EAF5F0] border border-[#C3E4D6] flex items-center justify-center text-[#287A68]">
                <CheckCircle2 className="w-8 h-8" />
              </div>

              <div>
                <h3 className="text-xl font-bold text-[#172B3A]">Registration Successful!</h3>
                <p className="mt-1.5 text-xs font-mono font-semibold text-[#087E8B] bg-[#DCEFF0] inline-block px-3 py-1 rounded-full border border-[#B5E1E4]">
                  {registeredEmail}
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#F7F8F6] border border-[#DCE4E3] text-left space-y-2">
                <p className="text-xs font-semibold text-[#172B3A] leading-relaxed">
                  Your account has been created. Please proceed to the Login page and sign in using your registered email and password.
                </p>
                <div className="pt-2 border-t border-[#DCE4E3] flex items-start gap-2 text-[11px] text-[#526773]">
                  <ShieldCheck className="w-4 h-4 text-[#087E8B] shrink-0 mt-0.5" />
                  <span>
                    {deliveryStatus === 'failed' || deliveryStatus === 'skipped_unconfigured' ? (
                      <>
                        <strong className="text-[#C24141]">Verification email could not be dispatched:</strong>{' '}
                        {deliveryError || 'Mail delivery is currently unavailable on this server.'}{' '}
                        Your account stays <strong>Unverified</strong> until OTP verification completes.
                      </>
                    ) : (
                      <>
                        <strong>Email verification pending:</strong> A 6-digit verification OTP has been accepted by the mail server for dispatch to{' '}
                        <span className="font-semibold text-[#172B3A]">{registeredEmail}</span>. Check your Inbox or Spam folder and enter the code to verify your account.
                      </>
                    )}
                  </span>
                </div>
              </div>

              <div className="space-y-2.5 pt-1">
                <button
                  type="button"
                  onClick={() => navigate('/login', { state: { email: registeredEmail } })}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] shadow-xs transition-colors"
                >
                  <span>Go to Login</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() =>
                    navigate('/verify-email', {
                      state: {
                        email: registeredEmail,
                        otpJustSent:
                          deliveryStatus === 'accepted_by_smtp' ||
                          deliveryStatus === 'accepted_by_provider',
                      },
                    })
                  }
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold text-[#087E8B] bg-[#DCEFF0] hover:bg-[#cde6e8] border border-[#B5E1E4] transition-colors"
                >
                  <Mail className="w-4 h-4" />
                  <span>Verify Email with 6-Digit OTP</span>
                </button>
              </div>
            </div>
          ) : (
            <>
              {localError && (
                <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-[#C24141] text-sm space-y-3">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 shrink-0 text-[#C24141] mt-0.5" />
                    <div className="text-xs leading-relaxed font-medium">{localError}</div>
                  </div>
                  {duplicateAccount && (
                    <div className="pl-8">
                      <button
                        type="button"
                        onClick={() => navigate('/login', { state: { email: email.trim().toLowerCase() } })}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#087E8B] hover:bg-[#075C66] text-white text-xs font-semibold transition-colors shadow-2xs"
                      >
                        <span>Go to Login</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div className="mb-6 p-3.5 rounded-xl bg-[#DCEFF0] border border-[#B5E1E4] text-[#075C66] text-xs flex items-center gap-2.5">
                <Shield className="w-4 h-4 text-[#087E8B] shrink-0" />
                <span>
                  All self-service registrations are provisioned as <strong>Employee</strong> accounts with RBAC protections.
                </span>
              </div>

              <form className="space-y-5" onSubmit={handleSubmit}>
                <div>
                  <label className="block text-xs font-semibold text-[#172B3A] mb-1.5 uppercase tracking-wider">
                    Full Name
                  </label>
                  <div className="relative rounded-lg">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#718096]">
                      <UserIcon className="h-4 w-4" />
                    </div>
                    <input
                      type="text"
                      required
                      disabled={submitting}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Jane Developer"
                      className="block w-full pl-10 pr-3 py-2.5 bg-white border border-[#DCE4E3] rounded-lg text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] text-sm transition-colors disabled:opacity-60"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#172B3A] mb-1.5 uppercase tracking-wider">
                    Corporate Email
                  </label>
                  <div className="relative rounded-lg">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#718096]">
                      <Mail className="h-4 w-4" />
                    </div>
                    <input
                      type="email"
                      required
                      disabled={submitting}
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="jane.developer@nexdesk.ai"
                      className="block w-full pl-10 pr-3 py-2.5 bg-white border border-[#DCE4E3] rounded-lg text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] text-sm transition-colors disabled:opacity-60"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#172B3A] mb-1.5 uppercase tracking-wider">
                    Password (min. 8 characters)
                  </label>
                  <div className="relative rounded-lg">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#718096]">
                      <Lock className="h-4 w-4" />
                    </div>
                    <input
                      type="password"
                      required
                      disabled={submitting}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="block w-full pl-10 pr-3 py-2.5 bg-white border border-[#DCE4E3] rounded-lg text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] text-sm transition-colors disabled:opacity-60"
                    />
                  </div>
                </div>

                <div>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full flex justify-center items-center gap-2 py-2.5 px-4 rounded-lg shadow-xs text-sm font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#087E8B] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Creating Account...</span>
                      </>
                    ) : (
                      <>
                        <span>Complete Registration</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </div>
              </form>

              <div className="mt-6 text-center text-xs text-[#526773]">
                Already have an account?{' '}
                <Link to="/login" className="font-semibold text-[#087E8B] hover:text-[#075C66]">
                  Sign in
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
