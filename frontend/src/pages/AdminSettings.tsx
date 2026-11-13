import { useState } from 'react';
import { useToast } from '../hooks/useToast';
import { Settings, Save, Shield, Database, Cpu, Lock } from 'lucide-react';

export const AdminSettings = () => {
  const { showToast } = useToast();
  const [groqModel, setGroqModel] = useState('llama-3.3-70b-versatile');
  const [jwtExpiryHours, setJwtExpiryHours] = useState('24');
  const [enableAuditStream, setEnableAuditStream] = useState(true);
  const [autoEscalateBreaches, setAutoEscalateBreaches] = useState(true);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    showToast({
      type: 'success',
      title: 'Settings Persisted',
      message: 'ITSM operational parameters updated successfully.',
    });
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-2 text-xs font-semibold text-[#087E8B] uppercase tracking-wider mb-1">
          <Settings className="w-3.5 h-3.5 text-[#087E8B]" />
          <span>Platform Administration</span>
        </div>
        <h1 className="text-2xl font-bold text-[#172B3A] tracking-tight">System Settings</h1>
        <p className="text-xs text-[#526773] mt-1">
          Configure global LLM agent parameters, security policies, and SLA breach monitors.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* AI & Groq Configuration */}
        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs space-y-4">
          <div className="flex items-center space-x-2.5 pb-3 border-b border-[#DCE4E3]">
            <Cpu className="w-4 h-4 text-[#087E8B]" />
            <h2 className="text-sm font-bold text-[#172B3A]">AI Agent Runtime Settings</h2>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <label className="block font-semibold text-[#172B3A] mb-1">Groq LLM Model Designation</label>
              <select
                value={groqModel}
                onChange={(e) => setGroqModel(e.target.value)}
                className="w-full px-3 py-2 border border-[#DCE4E3] rounded-lg bg-white text-[#172B3A] focus:outline-none focus:ring-2 focus:ring-[#087E8B]"
              >
                <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (Recommended for ITSM)</option>
                <option value="llama-3.1-8b-instant">llama-3.1-8b-instant (Fast Triage / Low Latency)</option>
                <option value="mixtral-8x7b-32768">mixtral-8x7b-32768 (Legacy)</option>
              </select>
              <span className="text-[11px] text-[#718096] mt-1 block">
                Primary model used by Tier 1 AI Agent and incident auto-categorization pipeline.
              </span>
            </div>
          </div>
        </div>

        {/* Security & Access Controls */}
        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs space-y-4">
          <div className="flex items-center space-x-2.5 pb-3 border-b border-[#DCE4E3]">
            <Shield className="w-4 h-4 text-purple-700" />
            <h2 className="text-sm font-bold text-[#172B3A]">Security &amp; Authentication</h2>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <label className="block font-semibold text-[#172B3A] mb-1">JWT Session Lifetime (Hours)</label>
              <input
                type="number"
                value={jwtExpiryHours}
                onChange={(e) => setJwtExpiryHours(e.target.value)}
                className="w-full px-3 py-2 border border-[#DCE4E3] rounded-lg text-[#172B3A] focus:outline-none focus:ring-2 focus:ring-[#087E8B]"
              >
              </input>
            </div>

            <div className="pt-2 flex items-center justify-between">
              <div>
                <div className="font-semibold text-[#172B3A]">Immutable Audit Event Logging</div>
                <div className="text-[11px] text-[#526773]">Record all admin actions and auth attempts to DB</div>
              </div>
              <input
                type="checkbox"
                checked={enableAuditStream}
                onChange={(e) => setEnableAuditStream(e.target.checked)}
                className="w-4 h-4 text-[#087E8B] rounded focus:ring-[#087E8B]"
              />
            </div>
          </div>
        </div>

        {/* ITSM Telemetry & Database */}
        <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs space-y-4">
          <div className="flex items-center space-x-2.5 pb-3 border-b border-[#DCE4E3]">
            <Database className="w-4 h-4 text-[#287A68]" />
            <h2 className="text-sm font-bold text-[#172B3A]">ITSM Engine &amp; Database</h2>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-[#172B3A]">Automated SLA Breach Escalation</div>
                <div className="text-[11px] text-[#526773]">Automatically ping on-call when ticket breaches threshold</div>
              </div>
              <input
                type="checkbox"
                checked={autoEscalateBreaches}
                onChange={(e) => setAutoEscalateBreaches(e.target.checked)}
                className="w-4 h-4 text-[#087E8B] rounded focus:ring-[#087E8B]"
              />
            </div>

            <div className="p-3 bg-[#EFF3F1] rounded-xl border border-[#DCE4E3] text-[#172B3A] flex items-center space-x-2 text-[11px]">
              <Lock className="w-3.5 h-3.5 text-[#718096]" />
              <span>Storage backend: SQLite (<code>nexdesk.db</code>) with ChromaDB vector store ready.</span>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-[#087E8B] hover:bg-[#075C66] text-white font-semibold text-xs shadow-xs transition-colors"
          >
            <Save className="w-4 h-4" />
            <span>Save Configuration</span>
          </button>
        </div>
      </form>
    </div>
  );
};
