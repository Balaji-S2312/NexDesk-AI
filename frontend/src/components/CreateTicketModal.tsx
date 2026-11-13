import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Bot,
  Users,
  CheckCircle2,
  Edit3,
} from 'lucide-react';
import { Modal } from './Modal';
import { PriorityBadge } from './PriorityBadge';
import { AdaptiveSelect } from './AdaptiveSelect';
import { CategoryIcon } from './CategoryIcon';
import { createTicketApi, classifyIncidentApi } from '../services/api';
import { useToast } from '../hooks/useToast';
import {
  CATEGORY_OPTIONS,
  IMPACT_OPTIONS,
  URGENCY_OPTIONS,
  previewPriority,
} from '../utils/ticketOptions';
import { ImpactLevel, Ticket, TicketCategoryValue, UrgencyLevel } from '../types/ticket';
import { IncidentClassificationResult } from '../types/classification';

export interface TicketPrefillData {
  title?: string;
  description?: string;
  category?: TicketCategoryValue;
  subcategory?: string;
  impact?: ImpactLevel;
  urgency?: UrgencyLevel;
  assignmentGroup?: string;
  summary?: string;
  recommendedAction?: string;
}

interface CreateTicketModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (ticket: Ticket) => void;
  initialData?: TicketPrefillData | null;
}

const inputCls =
  'w-full text-xs px-3 py-2 border border-[#DCE4E3] rounded-lg bg-white text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B] transition-colors';

export const CreateTicketModal: React.FC<CreateTicketModalProps> = ({
  isOpen,
  onClose,
  onCreated,
  initialData,
}) => {
  const { showToast } = useToast();

  // Natural Language Description input for AI Auto-Classification
  const [naturalInput, setNaturalInput] = useState('');
  const [classifying, setClassifying] = useState(false);
  const [classificationResult, setClassificationResult] =
    useState<IncidentClassificationResult | null>(null);

  // Form fields editable by the employee
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState<TicketCategoryValue>('software');
  const [subcategory, setSubcategory] = useState('');
  const [impact, setImpact] = useState<ImpactLevel>('medium');
  const [urgency, setUrgency] = useState<UrgencyLevel>('medium');
  const [assignmentGroup, setAssignmentGroup] = useState<string>('Tier 1 Service Desk');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      if (initialData) {
        setTitle(initialData.title || '');
        setDescription(initialData.description || '');
        setCategory(initialData.category || 'software');
        setSubcategory(initialData.subcategory || '');
        setImpact(initialData.impact || 'medium');
        setUrgency(initialData.urgency || 'medium');
        setAssignmentGroup(initialData.assignmentGroup || 'Tier 1 Service Desk');
        setNaturalInput(initialData.description || initialData.title || '');
      } else {
        reset();
      }
      setError(null);
    }
  }, [isOpen, initialData]);

  const reset = () => {
    setNaturalInput('');
    setClassificationResult(null);
    setTitle('');
    setDescription('');
    setCategory('software');
    setSubcategory('');
    setImpact('medium');
    setUrgency('medium');
    setAssignmentGroup('Tier 1 Service Desk');
    setError(null);
  };

  const handleClose = () => {
    if (submitting) return;
    reset();
    onClose();
  };

  const handleRunClassification = async (textToClassify?: string) => {
    const rawText = (textToClassify || naturalInput || description).trim();
    if (rawText.length < 5) {
      setError('Please provide at least a few words describing the problem to run AI classification.');
      return;
    }

    setClassifying(true);
    setError(null);

    try {
      const result = await classifyIncidentApi({ description: rawText });
      setClassificationResult(result);

      // Auto-populate editable form with AI recommendations
      setTitle(result.title);
      setCategory(result.category_value);
      setSubcategory(result.subcategory || '');
      setImpact(result.impact_value);
      setUrgency(result.urgency_value);
      setAssignmentGroup(result.assignment_group);

      if (!description.trim() || description.trim() === naturalInput.trim()) {
        const fullDesc = `${rawText}\n\n[AI Summary]: ${result.summary}\n[Recommended Action]: ${result.recommended_action}`;
        setDescription(fullDesc);
      }

      showToast({
        type: 'success',
        title: 'Incident Classified',
        message: `Recommended ${result.priority_label} -> ${result.assignment_group}`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'AI classification failed';
      setError(`Classification notice: ${msg}. You can still fill out the fields manually.`);
    } finally {
      setClassifying(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (title.trim().length < 5) {
      setError('Title must be at least 5 characters.');
      return;
    }
    if (description.trim().length < 10) {
      setError('Description must be at least 10 characters.');
      return;
    }
    setSubmitting(true);
    try {
      const ticket = await createTicketApi({
        title: title.trim(),
        description: description.trim(),
        category,
        subcategory: subcategory.trim() || undefined,
        impact,
        urgency,
      });
      showToast({
        type: 'success',
        title: 'Ticket Created',
        message: `${ticket.ticket_number} created with priority ${ticket.priority_label}.`,
      });
      reset();
      onCreated(ticket);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create ticket');
    } finally {
      setSubmitting(false);
    }
  };

  const currentPriority = previewPriority(impact, urgency);

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Create New IT Ticket"
      description="Use natural language for AI-assisted classification or fill out the fields manually."
      maxWidth="2xl"
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            className="px-3.5 py-2 text-xs font-semibold text-[#172B3A] bg-white border border-[#DCE4E3] rounded-lg hover:bg-[#EFF3F1]"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="create-ticket-form"
            disabled={submitting}
            className="px-4 py-2 text-xs font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] disabled:opacity-60 rounded-lg shadow-xs flex items-center gap-1.5 cursor-pointer disabled:cursor-not-allowed"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{submitting ? 'Creating Ticket...' : 'Confirm Ticket Creation'}</span>
          </button>
        </>
      }
    >
      <div className="space-y-4">

        {error && (
          <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {/* AI Natural Language Classifier Bar */}
        <div className="p-3.5 bg-[#EFF3F1] border border-[#DCE4E3] rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs font-bold text-[#172B3A]">
              <Sparkles className="w-4 h-4 text-[#087E8B]" />
              <span>AI-Assisted Incident Classification</span>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-[#DCEFF0] text-[#087E8B]">
                Module 8
              </span>
            </div>
            {classificationResult && (
              <span className="text-[11px] text-[#287A68] font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Signals Applied
              </span>
            )}
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={naturalInput}
              onChange={(e) => setNaturalInput(e.target.value)}
              placeholder="e.g. My company laptop suddenly stopped connecting to Wi-Fi."
              className="flex-1 text-xs px-3 py-2 border border-[#DCE4E3] rounded-lg bg-white text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] shadow-2xs"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleRunClassification();
                }
              }}
            />
            <button
              type="button"
              onClick={() => handleRunClassification()}
              disabled={classifying || !naturalInput.trim()}
              className="px-3.5 py-2 text-xs font-semibold text-white bg-[#087E8B] hover:bg-[#075C66] disabled:opacity-50 rounded-lg shadow-2xs flex items-center gap-1.5 shrink-0 transition-colors"
            >
              <Bot className="w-3.5 h-3.5" />
              <span>{classifying ? 'Analyzing...' : 'Auto-Classify'}</span>
            </button>
          </div>

          {/* Quick example prompts */}
          {!classificationResult && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px] text-[#526773]">
              <span className="font-semibold text-[#718096]">Try example:</span>
              <button
                type="button"
                onClick={() => {
                  const ex = 'My company laptop suddenly stopped connecting to Wi-Fi.';
                  setNaturalInput(ex);
                  handleRunClassification(ex);
                }}
                className="px-2 py-0.5 rounded-md bg-white border border-[#DCE4E3] hover:border-[#B5E1E4] hover:bg-[#DCEFF0] text-[#172B3A] hover:text-[#087E8B] transition-colors"
              >
                Wi-Fi connectivity failure
              </button>
              <button
                type="button"
                onClick={() => {
                  const ex = 'Received a suspicious phishing email asking for credentials.';
                  setNaturalInput(ex);
                  handleRunClassification(ex);
                }}
                className="px-2 py-0.5 rounded-md bg-white border border-[#DCE4E3] hover:border-[#B5E1E4] hover:bg-[#DCEFF0] text-[#172B3A] hover:text-[#087E8B] transition-colors"
              >
                Phishing email alert
              </button>
            </div>
          )}

          {/* AI-Generated Ticket Preview Banner */}
          {classificationResult && (
            <div className="mt-2.5 p-3 bg-white border border-blue-200 rounded-lg text-xs space-y-2 shadow-2xs">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <span className="font-bold text-slate-900 flex items-center gap-1.5">
                  <Edit3 className="w-3.5 h-3.5 text-blue-600" />
                  AI Classification Preview
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-slate-500">Recommended Priority:</span>
                  <PriorityBadge priority={currentPriority} />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
                <div className="p-2 rounded bg-slate-50 border border-slate-100">
                  <span className="text-slate-400 block font-semibold uppercase text-[9px]">Category</span>
                  <span className="font-bold text-slate-800">{classificationResult.category}</span>
                  {classificationResult.subcategory && (
                    <span className="text-slate-500 block text-[10px]">
                      {classificationResult.subcategory}
                    </span>
                  )}
                </div>

                <div className="p-2 rounded bg-slate-50 border border-slate-100">
                  <span className="text-slate-400 block font-semibold uppercase text-[9px]">Routing Group</span>
                  <span className="font-bold text-slate-800 flex items-center gap-1">
                    <Users className="w-3 h-3 text-blue-600" />
                    {classificationResult.assignment_group}
                  </span>
                  <span className="text-slate-500 block text-[10px]">Recommended by category</span>
                </div>

                <div className="p-2 rounded bg-slate-50 border border-slate-100">
                  <span className="text-slate-400 block font-semibold uppercase text-[9px]">Priority Rules</span>
                  <span className="font-bold text-slate-800">
                    {classificationResult.impact} × {classificationResult.urgency}
                  </span>
                  <span className="text-emerald-700 block text-[10px] font-semibold">
                    Backend ITIL Validated
                  </span>
                </div>
              </div>

              {classificationResult.summary && (
                <div className="text-[11px] text-slate-600">
                  <span className="font-semibold text-slate-700">Summary: </span>
                  {classificationResult.summary}
                </div>
              )}

              {classificationResult.recommended_action && (
                <div className="text-[11px] text-blue-800 bg-blue-50/70 p-2 rounded border border-blue-100">
                  <span className="font-semibold text-blue-900">Recommended Action: </span>
                  {classificationResult.recommended_action}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Review & Edit Ticket Form */}
        <form id="create-ticket-form" onSubmit={handleSubmit} className="space-y-3.5 pt-1">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Title <span className="text-slate-400 font-normal">(Review or edit)</span>
            </label>
            <input
              type="text"
              value={title}
              maxLength={255}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Laptop Wi-Fi connectivity failure"
              className={inputCls}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[#172B3A] mb-1">
                Confirm Category
              </label>
              <AdaptiveSelect
                label="Category"
                value={category}
                onChange={(val) => setCategory(val as TicketCategoryValue)}
                options={CATEGORY_OPTIONS.map((o) => ({
                  value: o.value,
                  label: o.label,
                  icon: <CategoryIcon category={o.value} className="w-4 h-4 text-[#087E8B]" />,
                }))}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Subcategory <span className="text-slate-400 font-normal">(Optional)</span>
              </label>
              <input
                type="text"
                value={subcategory}
                maxLength={100}
                onChange={(e) => setSubcategory(e.target.value)}
                placeholder="e.g. Wi-Fi, VPN, Outlook"
                className={inputCls}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[#172B3A] mb-1">Impact</label>
              <AdaptiveSelect
                label="Impact"
                value={impact}
                onChange={(val) => setImpact(val as ImpactLevel)}
                options={IMPACT_OPTIONS}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#172B3A] mb-1">Urgency</label>
              <AdaptiveSelect
                label="Urgency"
                value={urgency}
                onChange={(val) => setUrgency(val as UrgencyLevel)}
                options={URGENCY_OPTIONS}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Assignment Group
              </label>
              <div className="text-xs px-3 py-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-700 flex items-center justify-between">
                <span className="font-semibold truncate">{assignmentGroup}</span>
                <Users className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              </div>
            </div>
          </div>

          {/* Deterministic Priority Banner */}
          <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg px-3.5 py-2.5">
            <div>
              <span className="text-xs font-semibold text-slate-700 block">
                Calculated Priority (Deterministic ITIL Matrix)
              </span>
              <span className="text-[10px] text-slate-500">
                Derived from {impact.toUpperCase()} Impact × {urgency.toUpperCase()} Urgency
              </span>
            </div>
            <PriorityBadge priority={currentPriority} />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Description <span className="text-slate-400 font-normal">(Review or edit)</span>
            </label>
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the issue, steps to reproduce, or error messages..."
              className={inputCls}
            />
          </div>
        </form>
      </div>
    </Modal>
  );
};
