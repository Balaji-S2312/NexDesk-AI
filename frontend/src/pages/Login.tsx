import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Cpu, Lock, Mail, AlertCircle, ArrowRight, ShieldCheck, UserCheck } from 'lucide-react';

export const Login: React.FC = () => {
  const { login, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState(() => (location.state as { email?: string } | null)?.email || '');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setLocalError(null);
    clearError();

    if (!email || !password) {
      setLocalError('Please provide both email and password.');
      return;
    }

    setSubmitting(true);
    try {
      await login({ email: email.trim().toLowerCase(), password });
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const apiErr = err as Error & { status?: number };
      const msg = apiErr instanceof Error ? apiErr.message : '';
      if (apiErr?.status === 401 || msg.toLowerCase().includes('invalid email or password')) {
        setLocalError('Invalid email or password. Please check your credentials and try again.');
      } else {
        setLocalError(msg || 'Invalid email or password. Please check your credentials and try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const fillCredentials = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setLocalError(null);
    clearError();
  };

  return (
    <div className="min-h-screen bg-[#F7F8F6] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex p-3 bg-[#087E8B] rounded-2xl text-white shadow-md shadow-[#087E8B]/20 mb-4">
          <Cpu className="w-8 h-8" />
        </div>
        <h2 className="text-3xl font-extrabold text-[#172B3A] tracking-tight">NexDesk AI</h2>
        <p className="mt-1 text-sm text-[#526773]">Sign in to your enterprise ITSM workspace</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-sm rounded-2xl sm:px-10 border border-[#DCE4E3]">
          {(localError || error) && (
            <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-[#C24141] text-sm flex items-start gap-3">
              <AlertCircle className="w-5 h-5 shrink-0 text-[#C24141] mt-0.5" />
              <div>{localError || error}</div>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
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
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="employee@nexdesk.ai"
                  className="block w-full pl-10 pr-3 py-2.5 bg-white border border-[#DCE4E3] rounded-lg text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] text-sm transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#172B3A] mb-1.5 uppercase tracking-wider">
                Password
              </label>
              <div className="relative rounded-lg">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#718096]">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="block w-full pl-10 pr-3 py-2.5 bg-white border border-[#DCE4E3] rounded-lg text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] text-sm transition-colors"
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={submitting}
                className="w-full flex justify-center items-center gap-2 py-2.5 px-4 rounded-lg shadow-xs text-sm font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#087E8B] disabled:opacity-50 transition-colors"
              >
                {submitting ? 'Authenticating...' : 'Sign In'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </form>

          {/* Seeded Demo Credentials Helper (Dev or explicit demo-enabled builds only) */}
          {(!import.meta.env.PROD || import.meta.env.VITE_ENABLE_DEMO_LOGIN === 'true') && (
          <div className="mt-6 pt-6 border-t border-[#DCE4E3]">
            <p className="text-xs text-[#526773] font-medium mb-3 text-center">
              Demo-Only Quick Login:
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => fillCredentials('admin@nexdesk.ai', 'AdminPassword123!')}
                className="flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-lg bg-[#EFF3F1] hover:bg-[#DCEFF0] text-[#172B3A] text-xs font-medium border border-[#DCE4E3] hover:border-[#B5E1E4] transition-colors"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
                <span>Admin Demo</span>
              </button>
              <button
                type="button"
                onClick={() => fillCredentials('employee@nexdesk.ai', 'EmployeePassword123!')}
                className="flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-lg bg-[#EFF3F1] hover:bg-[#DCEFF0] text-[#172B3A] text-xs font-medium border border-[#DCE4E3] hover:border-[#B5E1E4] transition-colors"
              >
                <UserCheck className="w-3.5 h-3.5 text-[#087E8B]" />
                <span>Employee Demo</span>
              </button>
            </div>
          </div>
          )}

          <div className="mt-6 text-center text-xs text-[#526773] leading-relaxed">
            Already registered? Sign in using your existing email and password. New here?{' '}
            <Link to="/register" className="font-semibold text-[#087E8B] hover:text-[#075C66]">
              Create an account
            </Link>
            .
          </div>
        </div>
      </div>
    </div>
  );
};
