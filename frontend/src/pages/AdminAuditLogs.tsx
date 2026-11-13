import { useState } from 'react';
import { ShieldCheck, Download, Search, Filter } from 'lucide-react';

interface AuditItem {
  id: number;
  actor: string;
  action: string;
  resource: string;
  ip_address: string;
  timestamp: string;
  status: 'success' | 'failure';
}

const MOCK_AUDIT_LOGS: AuditItem[] = [
  {
    id: 101,
    actor: 'admin@nexdesk.ai',
    action: 'USER_LOGIN',
    resource: 'auth/login',
    ip_address: '127.0.0.1',
    timestamp: '2026-11-12 12:15:32 UTC',
    status: 'success',
  },
  {
    id: 102,
    actor: 'system',
    action: 'DATABASE_INITIALIZATION',
    resource: 'database/tables',
    ip_address: 'localhost',
    timestamp: '2026-11-12 11:30:00 UTC',
    status: 'success',
  },
  {
    id: 103,
    actor: 'admin@nexdesk.ai',
    action: 'SEED_DEMO_TICKETS',
    resource: 'api/dashboard/seed',
    ip_address: '127.0.0.1',
    timestamp: '2026-11-12 12:20:14 UTC',
    status: 'success',
  },
  {
    id: 104,
    actor: 'employee@nexdesk.ai',
    action: 'USER_LOGIN',
    resource: 'auth/login',
    ip_address: '192.168.1.45',
    timestamp: '2026-11-12 12:22:45 UTC',
    status: 'success',
  },
  {
    id: 105,
    actor: 'anonymous',
    action: 'UNAUTHORIZED_ACCESS_ATTEMPT',
    resource: 'api/auth/users',
    ip_address: '192.168.1.199',
    timestamp: '2026-11-12 12:25:10 UTC',
    status: 'failure',
  },
];

export const AdminAuditLogs = () => {
  const [logs] = useState<AuditItem[]>(MOCK_AUDIT_LOGS);
  const [search, setSearch] = useState('');

  const filtered = logs.filter(
    (l) =>
      l.actor.toLowerCase().includes(search.toLowerCase()) ||
      l.action.toLowerCase().includes(search.toLowerCase()) ||
      l.resource.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-[#087E8B] uppercase tracking-wider mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-[#087E8B]" />
            <span>Compliance &amp; Security</span>
          </div>
          <h1 className="text-2xl font-bold text-[#172B3A] tracking-tight">System Audit Logs</h1>
          <p className="text-xs text-[#526773] mt-1">
            Tamper-evident operational access logs, administrative mutations, and auth events.
          </p>
        </div>

        <button
          onClick={() => alert('Exporting encrypted compliance audit log CSV')}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-[#EFF3F1] text-[#172B3A] border border-[#DCE4E3] text-xs font-semibold shadow-2xs transition-colors"
        >
          <Download className="w-3.5 h-3.5 text-[#718096]" />
          <span>Export CSV</span>
        </button>
      </div>

      {/* Filter / Search */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-[#718096]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by actor, event code, resource path..."
            className="w-full pl-9 pr-3 py-2 bg-white border border-[#DCE4E3] rounded-xl text-xs text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B]"
          />
        </div>
        <button className="flex items-center space-x-1 px-3 py-2 bg-white border border-[#DCE4E3] rounded-xl text-xs font-semibold text-[#526773] hover:bg-[#EFF3F1]">
          <Filter className="w-3.5 h-3.5 text-[#718096]" />
          <span>Filter</span>
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#EFF3F1] border-b border-[#DCE4E3] text-[11px] font-bold uppercase text-[#526773] tracking-wider">
              <tr>
                <th className="py-3 px-4">Event Time (UTC)</th>
                <th className="py-3 px-4">Principal Actor</th>
                <th className="py-3 px-4">Action Code</th>
                <th className="py-3 px-4">Resource Target</th>
                <th className="py-3 px-4">Origin IP</th>
                <th className="py-3 px-4 text-right">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#DCE4E3]">
              {filtered.map((item) => (
                <tr key={item.id} className="hover:bg-[#EFF3F1]/50 transition-colors">
                  <td className="py-3 px-4 font-mono text-[#718096] text-[11px]">{item.timestamp}</td>
                  <td className="py-3 px-4 font-semibold text-[#172B3A]">{item.actor}</td>
                  <td className="py-3 px-4">
                    <span className="font-mono text-[11px] bg-[#EFF3F1] text-[#172B3A] px-2 py-0.5 rounded border border-[#DCE4E3]">
                      {item.action}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-[#526773] font-mono text-[11px]">{item.resource}</td>
                  <td className="py-3 px-4 text-[#718096] font-mono text-[11px]">{item.ip_address}</td>
                  <td className="py-3 px-4 text-right">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                        item.status === 'success'
                          ? 'bg-[#EAF5F0] text-[#287A68] border border-[#C3E4D6]'
                          : 'bg-rose-100 text-[#C24141] border border-rose-200'
                      }`}
                    >
                      {item.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
