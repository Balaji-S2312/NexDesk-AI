import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Cpu, Lock, Mail, User, AlertCircle, ArrowRight, Shield } from 'lucide-react';

export const Register: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const { register, clearError } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    clearError();

    if (!name || !email || !password) {
      setLocalError('All fields are required.');
      return;
    }

    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters long.');
      return;
    }

    setSubmitting(true);
    try {
      await register({ name, email, password });
      navigate('/', { replace: true });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setLocalError(err.message);
      } else {
        setLocalError('Registration failed. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F8F6] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex p-3 bg-[#087E8B] rounded-2xl text-white shadow-md shadow-[#087E8B]/20 mb-4">
          <Cpu className="w-8 h-8" />
        </div>
        <h2 className="text-3xl font-extrabold text-[#172B3A] tracking-tight">Create Account</h2>
        <p className="mt-1 text-sm text-[#526773]">Join the NexDesk AI enterprise support platform</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-sm rounded-2xl sm:px-10 border border-[#DCE4E3]">
          {localError && (
            <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-[#C24141] text-sm flex items-start gap-3">
              <AlertCircle className="w-5 h-5 shrink-0 text-[#C24141] mt-0.5" />
              <div>{localError}</div>
            </div>
          )}

          <div className="mb-6 p-3.5 rounded-xl bg-[#DCEFF0] border border-[#B5E1E4] text-[#075C66] text-xs flex items-center gap-2.5">
            <Shield className="w-4 h-4 text-[#087E8B] shrink-0" />
            <span>All self-service registrations are provisioned as <strong>Employee</strong> accounts with RBAC protections.</span>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="block text-xs font-semibold text-[#172B3A] mb-1.5 uppercase tracking-wider">
                Full Name
              </label>
              <div className="relative rounded-lg">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#718096]">
                  <User className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Developer"
                  className="block w-full pl-10 pr-3 py-2.5 bg-white border border-[#DCE4E3] rounded-lg text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] text-sm transition-colors"
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
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane.developer@nexdesk.ai"
                  className="block w-full pl-10 pr-3 py-2.5 bg-white border border-[#DCE4E3] rounded-lg text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] text-sm transition-colors"
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
                {submitting ? 'Creating Account...' : 'Complete Registration'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </form>

          <div className="mt-6 text-center text-xs text-[#526773]">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-[#087E8B] hover:text-[#075C66]">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
