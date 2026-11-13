import { useEffect, useState } from 'react';
import { Server, ShieldCheck, Database, Bot, Clock, UserCheck, Shield } from 'lucide-react';
import { checkBackendHealth } from '../services/api';
import { HealthResponse } from '../types/api';
import { HealthBadge } from '../components/HealthBadge';
import { useAuth } from '../hooks/useAuth';

export const Dashboard = () => {
  const { user, isAdmin } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await checkBackendHealth();
      setHealth(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to reach backend.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="space-y-8">
      {/* Welcome & Session Banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-6 rounded-xl bg-slate-800/80 border border-slate-700/60 shadow-lg">
        <div className="flex items-center space-x-4">
          <div className="p-3 bg-indigo-600/20 text-indigo-400 rounded-xl">
            {isAdmin ? <Shield className="w-8 h-8 text-purple-400" /> : <UserCheck className="w-8 h-8 text-indigo-400" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-100">Welcome, {user?.name}</h1>
              <span className={`px-2 py-0.5 text-xs font-semibold rounded-full border ${
                isAdmin
                  ? 'bg-purple-900/40 text-purple-300 border-purple-700/50'
                  : 'bg-indigo-900/40 text-indigo-300 border-indigo-700/50'
              }`}>
                {user?.role.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">Authenticated Session: <span className="text-slate-300 font-mono">{user?.email}</span></p>
          </div>
        </div>

        <HealthBadge
          health={health}
          loading={loading}
          error={error}
          onRefresh={fetchHealth}
        />
      </div>

      {/* Backend & Security Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-slate-800/60 border border-slate-700/50 flex items-center space-x-4">
          <div className="p-3 bg-blue-600/20 text-blue-400 rounded-lg">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-400">Authentication</div>
            <div className="text-sm font-semibold text-slate-200">JWT Bearer (HS256)</div>
            <div className="text-xs text-emerald-400 font-mono mt-0.5">Active & Validated</div>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-800/60 border border-slate-700/50 flex items-center space-x-4">
          <div className="p-3 bg-purple-600/20 text-purple-400 rounded-lg">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-400">Database Layer</div>
            <div className="text-sm font-semibold text-slate-200">SQLite + SQLAlchemy</div>
            <div className="text-xs text-purple-400 font-mono mt-0.5">9 Models Initialized</div>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-800/60 border border-slate-700/50 flex items-center space-x-4">
          <div className="p-3 bg-amber-600/20 text-amber-400 rounded-lg">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-400">Access Scope</div>
            <div className="text-sm font-semibold text-slate-200">{isAdmin ? 'Organization-Wide' : 'Own Records Only'}</div>
            <div className="text-xs text-amber-400 font-mono mt-0.5">RBAC Enforced</div>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-800/60 border border-slate-700/50 flex items-center space-x-4">
          <div className="p-3 bg-emerald-600/20 text-emerald-400 rounded-lg">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-400">Password Security</div>
            <div className="text-sm font-semibold text-slate-200">Bcrypt Salted Hash</div>
            <div className="text-xs text-emerald-400 font-mono mt-0.5">Never Plaintext</div>
          </div>
        </div>
      </div>

      {/* Diagnostics Panel */}
      <div className="p-6 rounded-xl bg-slate-800/40 border border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Clock className="w-4 h-4 text-slate-400" /> Gateway Diagnostics
        </h3>

        {health ? (
          <div className="bg-slate-900 rounded-lg p-4 font-mono text-xs text-slate-300 border border-slate-800 space-y-1">
            <div><span className="text-slate-500">Service:</span> {health.app_name}</div>
            <div><span className="text-slate-500">Status:</span> <span className="text-emerald-400">{health.status}</span></div>
            <div><span className="text-slate-500">Version:</span> {health.version}</div>
            <div><span className="text-slate-500">Environment:</span> {health.environment}</div>
            <div><span className="text-slate-500">Server Timestamp:</span> {health.timestamp}</div>
          </div>
        ) : (
          <div className="text-xs text-slate-500 italic py-2">
            {loading ? 'Polling backend /api/health...' : 'Backend response unavailable.'}
          </div>
        )}
      </div>
    </div>
  );
};
