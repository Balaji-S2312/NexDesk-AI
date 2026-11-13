import { useState, useEffect } from 'react';
import { useToast } from '../hooks/useToast';
import { getUsersApi } from '../services/api';
import { User } from '../types/auth';
import { Users, Shield, Plus, Mail } from 'lucide-react';
import { Modal } from '../components/Modal';

interface GroupInfo {
  id: number;
  name: string;
  description: string;
  tier: string;
  lead: string;
  memberCount: number;
}

const DEFAULT_GROUPS: GroupInfo[] = [
  {
    id: 1,
    name: 'Service Desk Tier 1',
    description: 'Initial triage, password resets, baseline workstation setup & self-service support.',
    tier: 'Tier 1',
    lead: 'Sarah Jenkins',
    memberCount: 8,
  },
  {
    id: 2,
    name: 'Network Infrastructure Support',
    description: 'VPN connectivity, routing, switches, edge firewalls & enterprise Wi-Fi troubleshooting.',
    tier: 'Tier 2',
    lead: 'David Chen',
    memberCount: 4,
  },
  {
    id: 3,
    name: 'SecOps & Identity Access',
    description: 'MFA re-enrolment, SAML SSO entitlements, privilege elevation and security breach audits.',
    tier: 'Tier 3',
    lead: 'Alex Rivera',
    memberCount: 3,
  },
  {
    id: 4,
    name: 'DevOps & Cloud Systems',
    description: 'Kubernetes cluster triage, CI/CD pipeline interruptions, database connection timeouts.',
    tier: 'Tier 3',
    lead: 'Elena Rostova',
    memberCount: 5,
  },
];

export const AdminAssignmentGroups = () => {
  const { showToast } = useToast();
  const [groups, setGroups] = useState<GroupInfo[]>(DEFAULT_GROUPS);
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupTier, setNewGroupTier] = useState('Tier 1');
  const [newGroupDesc, setNewGroupDesc] = useState('');

  useEffect(() => {
    const fetchUsers = async () => {
      setLoadingUsers(true);
      try {
        const data = await getUsersApi();
        setUsers(data);
      } catch (err: unknown) {
        // Non-blocking
        console.warn('Could not load users list for groups', err);
      } finally {
        setLoadingUsers(false);
      }
    };
    fetchUsers();
  }, []);

  const handleCreateGroup = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGroupName.trim()) {
      showToast({ type: 'warning', title: 'Name Required', message: 'Please give the group a title.' });
      return;
    }

    const created: GroupInfo = {
      id: Date.now(),
      name: newGroupName,
      description: newGroupDesc || 'Standard support queue routing group.',
      tier: newGroupTier,
      lead: 'Unassigned',
      memberCount: 1,
    };

    setGroups([created, ...groups]);
    showToast({
      type: 'success',
      title: 'Group Configured',
      message: `Assignment group "${newGroupName}" added to routing matrix.`,
    });
    setCreateModalOpen(false);
    setNewGroupName('');
    setNewGroupDesc('');
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-[#087E8B] uppercase tracking-wider mb-1">
            <Users className="w-3.5 h-3.5 text-[#087E8B]" />
            <span>Organizational Routing</span>
          </div>
          <h1 className="text-2xl font-bold text-[#172B3A] tracking-tight">Assignment Groups</h1>
          <p className="text-xs text-[#526773] mt-1">
            Configure functional engineering and support queues for automated ticket dispatch.
          </p>
        </div>

        <button
          onClick={() => setCreateModalOpen(true)}
          className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-[#087E8B] hover:bg-[#075C66] text-white text-xs font-semibold shadow-xs transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>New Assignment Group</span>
        </button>
      </div>

      {/* Groups Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {groups.map((group) => (
          <div
            key={group.id}
            className="bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs hover:border-[#087E8B] transition-colors flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center space-x-2.5">
                  <div className="p-2 bg-[#DCEFF0] text-[#087E8B] rounded-lg">
                    <Shield className="w-4 h-4" />
                  </div>
                  <h3 className="font-bold text-[#172B3A] text-sm">{group.name}</h3>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-[#EFF3F1] text-[#172B3A] border border-[#DCE4E3]">
                  {group.tier}
                </span>
              </div>
              <p className="text-xs text-[#526773] leading-relaxed mb-4">{group.description}</p>
            </div>

            <div className="pt-3 border-t border-[#DCE4E3] flex items-center justify-between text-xs text-[#526773]">
              <span className="font-medium text-[#172B3A]">Lead: {group.lead}</span>
              <span className="font-semibold text-[#087E8B] bg-[#DCEFF0] px-2 py-0.5 rounded text-[11px]">
                {group.memberCount} Members
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Directory of Platform Operators */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs space-y-4">
        <div>
          <h2 className="text-sm font-bold text-[#172B3A] uppercase tracking-wider">
            Active System Operators ({users.length})
          </h2>
          <p className="text-xs text-[#526773]">Live directory queried from SQLite database auth store</p>
        </div>

        {loadingUsers ? (
          <div className="text-xs text-[#718096] py-4">Fetching active users from backend...</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {users.map((u) => (
              <div
                key={u.id}
                className="flex items-center space-x-3 p-3 rounded-xl border border-[#DCE4E3] bg-[#EFF3F1]/40"
              >
                <div className="w-8 h-8 rounded-full bg-[#DCEFF0] text-[#087E8B] font-bold text-xs flex items-center justify-center shrink-0">
                  {u.name.charAt(0)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold text-slate-900 truncate">{u.name}</div>
                  <div className="text-[11px] text-slate-500 truncate flex items-center gap-1">
                    <Mail className="w-3 h-3 text-slate-400" />
                    <span>{u.email}</span>
                  </div>
                </div>
                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase shrink-0 ${
                    u.role === 'admin'
                      ? 'bg-purple-100 text-purple-700'
                      : 'bg-slate-200 text-slate-700'
                  }`}
                >
                  {u.role}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Add Assignment Group"
        description="Create a new routing queue for automated incident assignment."
        footer={
          <>
            <button
              type="button"
              onClick={() => setCreateModalOpen(false)}
              className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="group-form"
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg"
            >
              Save Group
            </button>
          </>
        }
      >
        <form id="group-form" onSubmit={handleCreateGroup} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Group Name</label>
            <input
              type="text"
              required
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              placeholder="e.g. Database Reliability Team"
              className="w-full text-xs px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Support Tier</label>
            <select
              value={newGroupTier}
              onChange={(e) => setNewGroupTier(e.target.value)}
              className="w-full text-xs px-3 py-2 border border-slate-200 rounded-lg bg-white"
            >
              <option value="Tier 1">Tier 1 - Helpdesk / Triage</option>
              <option value="Tier 2">Tier 2 - Specialized Engineering</option>
              <option value="Tier 3">Tier 3 - Core Infrastructure / DevOps</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Description</label>
            <textarea
              rows={3}
              value={newGroupDesc}
              onChange={(e) => setNewGroupDesc(e.target.value)}
              placeholder="Scope of incidents routed to this queue..."
              className="w-full text-xs px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </form>
      </Modal>
    </div>
  );
};
