import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Cpu,
  Loader2,
  Mail,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import {
  sendVerificationOtpApi,
  verifyEmailOtpApi,
  verifyEmailWithTokenApi,
} from '../services/api';
import { PENDING_VERIFY_EMAIL_KEY } from './Register';

const OTP_LENGTH = 6;
const DEFAULT_OTP_VALIDITY_SECONDS = 600;
const RESEND_COOLDOWN_SECONDS = 60;

export const VerifyEmail: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const location = useLocation();
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();

  const stateEmail = (location.state as { email?: string; otpJustSent?: boolean } | null)?.email;
  const otpJustSent = Boolean((location.state as { otpJustSent?: boolean } | null)?.otpJustSent);
  const storedPendingEmail = (() => {
    try {
      return sessionStorage.getItem(PENDING_VERIFY_EMAIL_KEY) || '';
    } catch {
      return '';
    }
  })();

  const [emailInput, setEmailInput] = useState<string>(
    user?.email || stateEmail || storedPendingEmail || ''
  );
  const [digits, setDigits] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const inputRefs = useRef<Array<HTMLInputElement | null>>([]);

  const [status, setStatus] = useState<'otp' | 'verifying_link' | 'success' | 'link_error'>(
    token ? 'verifying_link' : user?.email_verified ? 'success' : 'otp'
  );
  const [verifyingOtp, setVerifyingOtp] = useState(false);
  const [resending, setResending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(
    otpJustSent ? 'A 6-digit verification code has been sent to your registered email.' : null
  );
  const [cooldown, setCooldown] = useState<number>(otpJustSent ? RESEND_COOLDOWN_SECONDS : 0);
  const [expirySeconds, setExpirySeconds] = useState<number>(DEFAULT_OTP_VALIDITY_SECONDS);

  useEffect(() => {
    if (user?.email && !emailInput) {
      setEmailInput(user.email);
    }
    if (user?.email_verified && !token) {
      setStatus('success');
    }
  }, [user, token, emailInput]);

  // Handle legacy/backup direct link verification (?token=...)
  useEffect(() => {
    if (!token) return;
    let mounted = true;
    setStatus('verifying_link');
    setErrorMessage(null);

    verifyEmailWithTokenApi(token)
      .then(async () => {
        if (!mounted) return;
        try {
          sessionStorage.removeItem(PENDING_VERIFY_EMAIL_KEY);
        } catch {
          // ignore
        }
        if (refreshUser) await refreshUser();
        if (mounted) setStatus('success');
      })
      .catch((err: unknown) => {
        if (!mounted) return;
        setStatus('link_error');
        setErrorMessage(
          err instanceof Error ? err.message : 'Verification link is invalid or has expired.'
        );
      });

    return () => {
      mounted = false;
    };
  }, [token, refreshUser]);

  // Cooldown countdown timer for Resend OTP
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  // OTP 10-minute expiration countdown
  useEffect(() => {
    if (status !== 'otp' || expirySeconds <= 0) return;
    const timer = setTimeout(() => setExpirySeconds((s) => Math.max(0, s - 1)), 1000);
    return () => clearTimeout(timer);
  }, [status, expirySeconds]);

  const formatTimer = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return `${String(mins).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
  };

  const resolvedEmail = (user?.email || emailInput).trim().toLowerCase();
  const otpValue = digits.join('');

  const focusBox = (index: number) => {
    const target = inputRefs.current[index];
    if (target) {
      target.focus();
      target.select();
    }
  };

  const handleDigitChange = (index: number, raw: string) => {
    setErrorMessage(null);
    const numeric = raw.replace(/\D/g, '');
    if (!numeric) {
      const next = [...digits];
      next[index] = '';
      setDigits(next);
      return;
    }

    if (numeric.length > 1) {
      const next = [...digits];
      for (let i = 0; i < OTP_LENGTH - index && i < numeric.length; i++) {
        next[index + i] = numeric[i];
      }
      setDigits(next);
      const nextFocus = Math.min(OTP_LENGTH - 1, index + numeric.length);
      focusBox(nextFocus);
      return;
    }

    const next = [...digits];
    next[index] = numeric;
    setDigits(next);
    if (index < OTP_LENGTH - 1) {
      focusBox(index + 1);
    }
  };

  const handleDigitKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      e.preventDefault();
      const next = [...digits];
      if (next[index]) {
        next[index] = '';
        setDigits(next);
      } else if (index > 0) {
        next[index - 1] = '';
        setDigits(next);
        focusBox(index - 1);
      }
      return;
    }
    if (e.key === 'ArrowLeft' && index > 0) {
      e.preventDefault();
      focusBox(index - 1);
    } else if (e.key === 'ArrowRight' && index < OTP_LENGTH - 1) {
      e.preventDefault();
      focusBox(index + 1);
    }
  };

  const handlePasteOtp = (e: React.ClipboardEvent) => {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, OTP_LENGTH);
    if (!pasted) return;
    e.preventDefault();
    setErrorMessage(null);
    const next = Array(OTP_LENGTH).fill('');
    for (let i = 0; i < pasted.length; i++) {
      next[i] = pasted[i];
    }
    setDigits(next);
    focusBox(Math.min(OTP_LENGTH - 1, pasted.length));
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (verifyingOtp) return;

    setErrorMessage(null);
    setInfoMessage(null);

    if (!user && !resolvedEmail) {
      setErrorMessage('Please enter your registered email address.');
      return;
    }

    if (otpValue.length !== OTP_LENGTH) {
      setErrorMessage('Please enter all 6 digits of your verification code.');
      return;
    }

    setVerifyingOtp(true);
    try {
      await verifyEmailOtpApi(otpValue, user ? undefined : resolvedEmail);
      try {
        sessionStorage.removeItem(PENDING_VERIFY_EMAIL_KEY);
      } catch {
        // ignore
      }
      if (refreshUser) {
        await refreshUser();
      }
      setStatus('success');
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Invalid or expired verification code.');
    } finally {
      setVerifyingOtp(false);
    }
  };

  const handleResendOtp = async () => {
    if (resending || cooldown > 0) return;
    setErrorMessage(null);
    setInfoMessage(null);

    if (!user && !resolvedEmail) {
      setErrorMessage('Please enter your registered email address first.');
      return;
    }

    setResending(true);
    try {
      const res = await sendVerificationOtpApi(user ? undefined : resolvedEmail);
      if (res.already_verified) {
        if (refreshUser) await refreshUser();
        setStatus('success');
        return;
      }
      setDigits(Array(OTP_LENGTH).fill(''));
      setExpirySeconds(res.expires_in_seconds || DEFAULT_OTP_VALIDITY_SECONDS);
      setCooldown(res.cooldown_seconds || RESEND_COOLDOWN_SECONDS);
      setInfoMessage('A fresh 6-digit verification code has been sent to your email.');
      focusBox(0);
    } catch (err: unknown) {
      const apiErr = err as Error & { status?: number };
      const msg = apiErr instanceof Error ? apiErr.message : 'Failed to send verification code.';
      setErrorMessage(msg);
      const match = msg.match(/wait (\d+) seconds/i);
      if (match) {
        setCooldown(Number(match[1]));
      }
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F8F6] flex flex-col justify-center py-10 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-6">
        <div className="inline-flex p-3 bg-[#087E8B] rounded-2xl text-white shadow-md shadow-[#087E8B]/20 mb-3">
          <Cpu className="w-8 h-8" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-[#172B3A] tracking-tight">
          Verify Your Email Address
        </h1>
        <p className="mt-1 text-xs sm:text-sm text-[#526773]">
          NexDesk AI Enterprise Security &bull; 6-Digit Email OTP Verification
        </p>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white border border-[#DCE4E3] py-8 px-5 sm:px-9 shadow-sm rounded-2xl">
          {status === 'verifying_link' && (
            <div className="text-center py-6 space-y-3">
              <Loader2 className="w-11 h-11 text-[#087E8B] animate-spin mx-auto" />
              <h2 className="text-lg font-bold text-[#172B3A]">Verifying Your Email...</h2>
              <p className="text-xs text-[#526773]">
                Validating your single-use verification token with NexDesk AI.
              </p>
            </div>
          )}

          {status === 'success' && (
            <div className="text-center py-3 space-y-5">
              <div className="w-14 h-14 bg-[#EAF5F0] text-[#287A68] rounded-full flex items-center justify-center mx-auto border border-[#C3E4D6]">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-[#172B3A]">Email Verified Successfully!</h2>
                <p className="mt-2 text-xs sm:text-sm text-[#526773] leading-relaxed">
                  Your email address has been verified. You can now submit IT support tickets and receive real-time email notifications.
                </p>
              </div>
              <div className="space-y-2.5">
                {user ? (
                  <>
                    <button
                      type="button"
                      onClick={() => navigate('/profile')}
                      className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] shadow-xs transition-colors"
                    >
                      <span>Back to Profile</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => navigate('/')}
                      className="w-full py-2.5 px-4 rounded-xl text-xs font-semibold text-[#172B3A] bg-[#F7F8F6] hover:bg-[#EFF3F1] border border-[#DCE4E3] transition-colors"
                    >
                      Go to Dashboard
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => navigate('/login', { state: { email: resolvedEmail } })}
                    className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] shadow-xs transition-colors"
                  >
                    <span>Continue to Login</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          )}

          {(status === 'otp' || status === 'link_error') && (
            <div className="space-y-5">
              {status === 'link_error' && (
                <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-[#C24141] text-xs flex items-start gap-2.5">
                  <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold">Verification link invalid or expired</p>
                    <p className="mt-0.5">{errorMessage}</p>
                    <button
                      type="button"
                      onClick={() => {
                        setStatus('otp');
                        setErrorMessage(null);
                      }}
                      className="mt-2 font-semibold underline text-[#087E8B] hover:text-[#075C66]"
                    >
                      Switch to 6-Digit OTP Verification &rarr;
                    </button>
                  </div>
                </div>
              )}

              {status === 'otp' && (
                <form onSubmit={handleVerifyOtp} className="space-y-5">
                  <div className="flex items-center justify-between gap-2 p-3 rounded-xl bg-[#DCEFF0]/60 border border-[#B5E1E4]">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <ShieldCheck className="w-4 h-4 text-[#087E8B] shrink-0" />
                      <div className="min-w-0">
                        <span className="block text-[10px] font-bold uppercase tracking-wider text-[#075C66]">
                          Registered Email
                        </span>
                        {user?.email ? (
                          <span className="block text-xs font-mono font-semibold text-[#172B3A] truncate">
                            {user.email}
                          </span>
                        ) : (
                          <input
                            type="email"
                            required
                            value={emailInput}
                            onChange={(e) => setEmailInput(e.target.value)}
                            placeholder="employee@nexdesk.ai"
                            aria-label="Registered Email Address"
                            className="mt-0.5 w-full bg-white border border-[#DCE4E3] rounded-lg px-2.5 py-1 text-xs font-mono text-[#172B3A] focus:outline-none focus:ring-2 focus:ring-[#087E8B]"
                          />
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 text-[11px] font-mono font-semibold text-[#075C66] bg-white px-2.5 py-1 rounded-lg border border-[#B5E1E4] shrink-0">
                      <Clock className="w-3.5 h-3.5 text-[#087E8B]" />
                      <span>{formatTimer(expirySeconds)}</span>
                    </div>
                  </div>

                  {infoMessage && (
                    <div
                      role="status"
                      className="p-3 rounded-xl bg-[#EAF5F0] border border-[#C3E4D6] text-[#287A68] text-xs flex items-center gap-2"
                    >
                      <Mail className="w-4 h-4 shrink-0" />
                      <span>{infoMessage}</span>
                    </div>
                  )}

                  {errorMessage && (
                    <div
                      role="alert"
                      className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-[#C24141] text-xs flex items-start gap-2"
                    >
                      <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
                      <span>{errorMessage}</span>
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-semibold text-[#172B3A] text-center mb-3">
                      Enter the 6-digit verification code sent to your email
                    </label>
                    <div
                      className="flex items-center justify-center gap-2 sm:gap-2.5"
                      onPaste={handlePasteOtp}
                    >
                      {digits.map((digit, idx) => (
                        <input
                          key={idx}
                          ref={(el) => {
                            inputRefs.current[idx] = el;
                          }}
                          type="text"
                          inputMode="numeric"
                          pattern="\d*"
                          maxLength={1}
                          value={digit}
                          disabled={verifyingOtp}
                          aria-label={`Verification code digit ${idx + 1}`}
                          onChange={(e) => handleDigitChange(idx, e.target.value)}
                          onKeyDown={(e) => handleDigitKeyDown(idx, e)}
                          className="w-10 h-12 sm:w-12 sm:h-14 text-center text-lg sm:text-xl font-bold font-mono text-[#172B3A] bg-white border border-[#DCE4E3] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] transition-all shadow-2xs disabled:opacity-60"
                        />
                      ))}
                    </div>
                    <p className="mt-2.5 text-[11px] text-center text-[#526773]">
                      Tip: You can paste all 6 digits directly into any box.
                    </p>
                  </div>

                  <button
                    type="submit"
                    disabled={verifyingOtp || otpValue.length !== OTP_LENGTH}
                    className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] disabled:opacity-50 disabled:cursor-not-allowed shadow-xs transition-colors"
                  >
                    {verifyingOtp ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Verifying Email...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="w-4 h-4" />
                        <span>Verify Email</span>
                      </>
                    )}
                  </button>

                  <div className="pt-2 border-t border-[#DCE4E3] flex flex-col sm:flex-row items-center justify-between gap-2 text-xs">
                    <span className="text-[#526773]">Didn't receive a code?</span>
                    <button
                      type="button"
                      onClick={handleResendOtp}
                      disabled={resending || cooldown > 0}
                      className="inline-flex items-center gap-1.5 font-semibold text-[#087E8B] hover:text-[#075C66] disabled:text-[#526773] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${resending ? 'animate-spin' : ''}`} />
                      <span>
                        {resending
                          ? 'Sending OTP...'
                          : cooldown > 0
                          ? `Resend OTP in ${cooldown}s`
                          : 'Resend OTP'}
                      </span>
                    </button>
                  </div>
                </form>
              )}

              <div className="pt-4 border-t border-[#DCE4E3] text-center text-xs text-[#526773]">
                {user ? (
                  <Link to="/profile" className="font-semibold text-[#087E8B] hover:text-[#075C66]">
                    Return to Profile
                  </Link>
                ) : (
                  <>
                    Already verified?{' '}
                    <Link to="/login" className="font-semibold text-[#087E8B] hover:text-[#075C66]">
                      Sign In
                    </Link>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
