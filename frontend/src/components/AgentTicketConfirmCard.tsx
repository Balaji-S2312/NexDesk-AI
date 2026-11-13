import React, { useState } from 'react';
import {
  CheckCircle2,
  ExternalLink,
  ShieldCheck,
  Users,
  XCircle,
  Wrench,
  BookOpen,
} from 'lucide-react';
import { AgentConfirmPayload, AgentConfirmResponse, PendingTicketAction } from '../types/agent';
import { ImpactLevel, TicketCategoryValue, UrgencyLevel } from '../types/ticket';
import {
  CATEGORY_OPTIONS,
  IMPACT_OPTIONS,
  URGENCY_OPTIONS,
  previewPriority,
} from '../utils/ticketOptions';
import { PriorityBadge } from './PriorityBadge';

interface AgentTicketConfirmCardProps {
  pendingAction: PendingTicketAction;
  onConfirm: (payload: AgentConfirmPayload) => Promise<AgentConfirmResponse>;
  onCancel: (confirmationId: string) => Promise<void>;
  onViewTicket: (ticketId: number) => void;
}

const inputCls =
  'w-full text-[11px] px-2.5 py-1.5 border border-[#DCE4E3] rounded-lg bg-white text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] transition-colors';

export const AgentTicketConfirmCard: React.FC<AgentTicketConfirmCardProps> = ({
  pendingAction,
  onConfirm,
  onCancel,
  onViewTicket,
}) => {
  const [title, setTitle] = useState(pendingAction.title);
  const [description, setDescription] = useState(pendingAction.description);
  const [category, setCategory] = useState<TicketCategoryValue>(pendingAction.category_value);
  const [subcategory, setSubcategory] = useState(pendingAction.subcategory || '');
  const [impact, setImpact] = useState<ImpactLevel>(pendingAction.impact_value);
  const [urgency, setUrgency] = useState<UrgencyLevel>(pendingAction.urgency_value);
  const [submitting, setSubmitting] = useState(false);

  const livePriority = previewPriority(impact, urgency);

  if (pendingAction.status === 'confirmed') {
    return (
      <div className="mt-3 p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl text-xs space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 font-bold text-emerald-900">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>
              Ticket Confirmed &amp; Created: {pendingAction.created_ticket_number}
            </span>
          </div>
          <PriorityBadge priority={livePriority} />
        </div>
        <div className="text-[11px] text-emerald-800">
          Routed to <span className="font-semibold">{pendingAction.assignment_group}</span> with troubleshooting history and knowledge references attached.
        </div>
        {pendingAction.created_ticket_id && (
          <button
            type="button"
            onClick={() => onViewTicket(pendingAction.created_ticket_id!)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-[11px] font-semibold transition-colors"
          >
            <span>View Ticket {pendingAction.created_ticket_number}</span>
            <ExternalLink className="w-3 h-3" />
          </button>
        )}
      </div>
    );
  }

  if (pendingAction.status === 'cancelled') {
    return (
      <div className="mt-3 p-3 bg-slate-100 border border-slate-200 rounded-xl text-[11px] text-slate-600 flex items-center gap-2">
        <XCircle className="w-4 h-4 text-slate-500" />
        <span>Ticket draft cancelled. No incident was created.</span>
      </div>
    );
  }

  const handleConfirmClick = async () => {
    setSubmitting(true);
    try {
      await onConfirm({
        confirmation_id: pendingAction.confirmation_id,
        title: title.trim(),
        description: description.trim(),
        category,
        subcategory: subcategory.trim() || undefined,
        impact,
        urgency,
        assignment_group: pendingAction.assignment_group,
        escalate_to_human: true,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelClick = async () => {
    setSubmitting(true);
    try {
      await onCancel(pendingAction.confirmation_id);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mt-3 p-3.5 bg-white border border-blue-200 rounded-xl shadow-xs space-y-3 text-slate-800">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
        <div className="flex items-center gap-1.5 text-xs font-bold text-blue-900">
          <ShieldCheck className="w-4 h-4 text-blue-600" />
          <span>Human-in-the-Loop Ticket Preview</span>
        </div>
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          Awaiting Confirmation
        </span>
      </div>

      <p className="text-[11px] text-slate-500">
        No ticket has been created yet. Review or edit the prepared details and confirm to escalate to{' '}
        <span className="font-semibold text-slate-800">{pendingAction.assignment_group}</span>.
      </p>

      <div className="space-y-2">
        <div>
          <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-0.5">Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputCls}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-0.5">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as TicketCategoryValue)}
              className={inputCls}
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-0.5">Subcategory</label>
            <input
              type="text"
              value={subcategory}
              onChange={(e) => setSubcategory(e.target.value)}
              className={inputCls}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-0.5">Impact</label>
            <select
              value={impact}
              onChange={(e) => setImpact(e.target.value as ImpactLevel)}
              className={inputCls}
            >
              {IMPACT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-0.5">Urgency</label>
            <select
              value={urgency}
              onChange={(e) => setUrgency(e.target.value as UrgencyLevel)}
              className={inputCls}
            >
              {URGENCY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-[11px]">
          <div className="flex items-center gap-1.5 text-slate-700">
            <Users className="w-3.5 h-3.5 text-blue-600" />
            <span>
              Assignment Group: <strong className="text-slate-900">{pendingAction.assignment_group}</strong>
            </span>
          </div>
          <PriorityBadge priority={livePriority} />
        </div>

        <div>
          <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-0.5">Description</label>
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={inputCls}
          />
        </div>

        {pendingAction.attempted_troubleshooting.length > 0 && (
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-[10px] text-slate-600 space-y-1">
            <div className="font-semibold text-slate-700 flex items-center gap-1">
              <Wrench className="w-3 h-3 text-slate-500" />
              Attempted Troubleshooting Included in Escalation:
            </div>
            <ul className="list-disc pl-4 space-y-0.5">
              {pendingAction.attempted_troubleshooting.slice(0, 3).map((step, idx) => (
                <li key={idx}>{step}</li>
              ))}
            </ul>
          </div>
        )}

        {pendingAction.retrieved_sources.length > 0 && (
          <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
            <BookOpen className="w-3 h-3 text-blue-600" />
            <span>
              KB References attached:{' '}
              {pendingAction.retrieved_sources
                .slice(0, 2)
                .map((s) => `${String(s.filename || s.title)} (p.${String(s.page_number || 1)})`)
                .join(', ')}
            </span>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
        <button
          type="button"
          disabled={submitting}
          onClick={handleCancelClick}
          className="px-3 py-1.5 text-[11px] font-semibold text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={handleConfirmClick}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-[11px] font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] rounded-lg shadow-2xs disabled:opacity-50 transition-colors"
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>{submitting ? 'Creating & Escalating...' : 'Confirm & Create Ticket'}</span>
        </button>
      </div>
    </div>
  );
};
