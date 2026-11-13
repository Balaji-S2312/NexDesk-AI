import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bot,
  Send,
  User,
  Sparkles,
  HelpCircle,
  PlusCircle,
  FileText,
  RotateCcw,
  AlertCircle,
  CheckCircle2,
  XCircle,
  BookOpen,
  MessageSquarePlus,
  Database,
  Cpu,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import {
  sendChatMessageApi,
  confirmAgentTicketApi,
  cancelAgentTicketApi,
  ChatSourceItem,
  ChatActionItem,
} from '../services/api';
import { CreateTicketModal, TicketPrefillData } from '../components/CreateTicketModal';
import { AgentTicketConfirmCard } from '../components/AgentTicketConfirmCard';
import { AgentConfirmPayload, AgentToolExecution, PendingTicketAction } from '../types/agent';
import { ImpactLevel, Ticket, TicketCategoryValue, UrgencyLevel } from '../types/ticket';

interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  content: string;
  timestamp: string;
  sources?: ChatSourceItem[];
  actions?: ChatActionItem[];
  followUpQuestions?: string[];
  ragUsed?: boolean;
  retrievedChunksCount?: number;
  toolCalls?: AgentToolExecution[];
  pendingAction?: PendingTicketAction | null;
  feedback?: 'resolved' | 'not_resolved';
  isWelcome?: boolean;
  isError?: boolean;
}

const VALID_CATEGORIES = new Set<TicketCategoryValue>([
  'hardware',
  'software',
  'network',
  'access_management',
  'email',
  'security',
  'other',
]);

const VALID_LEVELS = new Set<ImpactLevel>(['low', 'medium', 'high']);

function extractPrefillFromAction(action?: ChatActionItem, fallbackContent?: string): TicketPrefillData {
  const payload = action?.payload || {};
  const rawCategory = typeof payload.category === 'string' ? payload.category : 'other';
  const rawImpact = typeof payload.impact === 'string' ? payload.impact : 'medium';
  const rawUrgency = typeof payload.urgency === 'string' ? payload.urgency : 'medium';

  return {
    title: typeof payload.title === 'string' ? payload.title : 'AI Support Escalation',
    description:
      typeof payload.description === 'string'
        ? payload.description
        : fallbackContent || 'Escalated from NexDesk AI support conversation.',
    category: VALID_CATEGORIES.has(rawCategory as TicketCategoryValue)
      ? (rawCategory as TicketCategoryValue)
      : 'other',
    subcategory: typeof payload.subcategory === 'string' ? payload.subcategory : '',
    impact: VALID_LEVELS.has(rawImpact as ImpactLevel) ? (rawImpact as ImpactLevel) : 'medium',
    urgency: VALID_LEVELS.has(rawUrgency as UrgencyLevel) ? (rawUrgency as UrgencyLevel) : 'medium',
  };
}

export const AISupport: React.FC = () => {
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-msg',
      sender: 'agent',
      content: `Hello ${user?.name || 'there'}! I am your NexDesk AI IT Assistant grounded in your organization's Knowledge Base. Ask any IT troubleshooting or policy question and I will retrieve matching runbooks and cite exact pages.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      isWelcome: true,
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [ticketModalOpen, setTicketModalOpen] = useState(false);
  const [ticketPrefill, setTicketPrefill] = useState<TicketPrefillData | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const suggestedPrompts = [
    'How can I reset my VPN password?',
    'My VPN is still not working after following the instructions.',
    'How do I get a temporary YubiKey MFA bypass code?',
    "What is our company's Mars exploration policy?",
  ];

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const data = await sendChatMessageApi({
        conversation_id: conversationId,
        message: query,
      });

      if (data.conversation_id) {
        setConversationId(data.conversation_id);
      }

      const agentMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        content: data.response,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: data.sources || [],
        actions: data.actions || [],
        followUpQuestions: data.follow_up_questions || [],
        ragUsed: Boolean(data.rag_used),
        retrievedChunksCount: data.retrieved_chunks_count ?? (data.sources?.length || 0),
        toolCalls: data.tool_calls || [],
        pendingAction: data.pending_action || null,
      };

      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: unknown) {
      const errorText = err instanceof Error ? err.message : 'Unable to connect to AI Service.';
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        content: `Error: ${errorText}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
      showToast({
        type: 'error',
        title: 'AI Service Error',
        message: errorText,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateTicket = (msg?: ChatMessage) => {
    const createAction = msg?.actions?.find((a) => a.action_type === 'create_ticket');
    setTicketPrefill(extractPrefillFromAction(createAction, msg?.content));
    setTicketModalOpen(true);
  };

  const handleConfirmPendingTicket = async (msgId: string, payload: AgentConfirmPayload) => {
    const res = await confirmAgentTicketApi(payload);
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId && m.pendingAction
          ? {
              ...m,
              pendingAction: {
                ...m.pendingAction,
                status: 'confirmed',
                created_ticket_id: res.ticket.id,
                created_ticket_number: res.ticket.ticket_number,
              },
            }
          : m
      )
    );
    window.dispatchEvent(new Event('nexdesk-notifications-updated'));
    showToast({
      type: 'success',
      title: 'Ticket Confirmed & Escalated',
      message: res.message,
    });
    return res;
  };

  const handleCancelPendingTicket = async (msgId: string, confirmationId: string) => {
    await cancelAgentTicketApi(confirmationId);
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId && m.pendingAction
          ? {
              ...m,
              pendingAction: { ...m.pendingAction, status: 'cancelled' },
            }
          : m
      )
    );
    showToast({
      type: 'info',
      title: 'Draft Cancelled',
      message: 'Pending ticket preparation was cancelled.',
    });
  };

  const handleFeedback = (msgId: string, status: 'resolved' | 'not_resolved') => {
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId ? { ...m, feedback: status } : m))
    );
    const targetMsg = messages.find((m) => m.id === msgId);
    if (status === 'resolved') {
      showToast({
        type: 'success',
        title: 'Issue Marked Resolved',
        message: 'Glad our Knowledge Base and AI guidance solved your issue.',
      });
    } else {
      showToast({
        type: 'info',
        title: 'Ready to Escalate',
        message: 'We prefilled an IT support ticket from this conversation.',
      });
      handleOpenCreateTicket(targetMsg);
    }
  };

  const handleResetConversation = () => {
    setConversationId(null);
    setMessages([
      {
        id: Date.now().toString(),
        sender: 'agent',
        content: 'Conversation refreshed. Ask any IT troubleshooting or policy question to begin.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isWelcome: true,
      },
    ]);
  };

  const handleTicketCreated = (ticket: Ticket) => {
    setTicketModalOpen(false);
    setTicketPrefill(null);
    showToast({
      type: 'success',
      title: 'Ticket Provisioned',
      message: `Incident ${ticket.ticket_number} created successfully.`,
    });
    navigate(`/tickets/${ticket.id}`);
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-8.5rem)] flex flex-col bg-white rounded-2xl border border-[#DCE4E3] shadow-xs overflow-hidden transition-colors">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#DCE4E3] flex items-center justify-between bg-[#EFF3F1]/60">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-[#087E8B] rounded-xl text-white shadow-xs">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-bold text-[#172B3A] leading-tight">NexDesk AI Assistant</h2>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-[#DCEFF0] text-[#087E8B]">
                RAG + Groq LLM
              </span>
            </div>
            <p className="text-[11px] text-[#526773]">
              Grounded in ChromaDB company runbooks with live ticket escalation
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => navigate('/knowledge-base')}
            className="px-2.5 py-1.5 text-[#172B3A] hover:text-[#087E8B] hover:bg-[#DCEFF0] rounded-lg transition-colors text-xs flex items-center gap-1 border border-[#DCE4E3] bg-white"
            title="View indexed Knowledge Base documents"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Knowledge Base</span>
          </button>
          <button
            onClick={handleResetConversation}
            className="p-1.5 text-[#718096] hover:text-[#172B3A] hover:bg-[#EFF3F1] rounded-lg transition-colors text-xs flex items-center gap-1"
            title="Start new conversation"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="text-xs hidden sm:inline">New Chat</span>
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start space-x-3 ${msg.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
                msg.sender === 'user'
                  ? 'bg-[#EFF3F1] text-[#172B3A] border border-[#DCE4E3]'
                  : msg.isError
                  ? 'bg-rose-100 text-[#C24141]'
                  : 'bg-[#087E8B] text-white shadow-xs'
              }`}
            >
              {msg.sender === 'user' ? (
                <User className="w-4 h-4" />
              ) : msg.isError ? (
                <AlertCircle className="w-4 h-4" />
              ) : (
                <Bot className="w-4 h-4" />
              )}
            </div>

            {/* Content Bubble */}
            <div className="max-w-[84%] space-y-2">
              <div
                className={`p-4 rounded-2xl text-xs leading-relaxed ${
                  msg.sender === 'user'
                    ? 'bg-[#087E8B] text-white rounded-tr-none'
                    : msg.isError
                    ? 'bg-rose-50 border border-rose-200 text-[#C24141] rounded-tl-none'
                    : 'bg-[#EFF3F1] border border-[#DCE4E3] text-[#172B3A] rounded-tl-none'
                }`}
              >
                {/* Retrieved Document Indicator */}
                {msg.sender === 'agent' && !msg.isWelcome && !msg.isError && (
                  <div className="mb-2.5 flex items-center">
                    {msg.ragUsed ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-[#DCEFF0] text-[#087E8B] border border-[#B5E1E4]">
                        <Database className="w-3 h-3" />
                        Grounded in {msg.retrievedChunksCount || msg.sources?.length || 1} retrieved KB source
                        {(msg.retrievedChunksCount || msg.sources?.length || 1) === 1 ? '' : 's'}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                        <AlertCircle className="w-3 h-3" />
                        No matching KB documentation found above threshold
                      </span>
                    )}
                  </div>
                )}

                {/* Executed Backend Tools (Module 9 Agentic Orchestration) */}
                {msg.sender === 'agent' && msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div className="mb-2.5 flex flex-wrap items-center gap-1.5" data-testid="agent-tool-badges">
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-500 mr-1">
                      <Cpu className="w-3 h-3 text-indigo-600" />
                      Agent Tools:
                    </span>
                    {msg.toolCalls.map((tc, idx) => (
                      <span
                        key={`${tc.tool_name}-${idx}`}
                        title={tc.summary}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold border ${
                          tc.status === 'success'
                            ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                            : tc.status === 'blocked'
                            ? 'bg-rose-50 text-rose-700 border-rose-200'
                            : 'bg-amber-50 text-amber-700 border-amber-200'
                        }`}
                      >
                        {tc.tool_name}
                      </span>
                    ))}
                  </div>
                )}

                <div className="whitespace-pre-wrap">{msg.content}</div>

                {/* Knowledge Source Cards */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3.5 pt-3 border-t border-slate-200/70 space-y-2">
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-blue-600" />
                      Retrieved Knowledge Sources ({msg.sources.length})
                    </div>
                    <div className="grid grid-cols-1 gap-2">
                      {msg.sources.map((src, i) => (
                        <div
                          key={src.id || i}
                          className="bg-white border border-slate-200 rounded-xl p-2.5 text-[11px] text-slate-600 shadow-2xs"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                              <FileText className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                              <span>{src.filename || src.title}</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              {src.page_number !== undefined && src.page_number !== null && (
                                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold text-[10px]">
                                  Page {src.page_number}
                                </span>
                              )}
                              {src.score !== undefined && src.score !== null && (
                                <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold text-[10px]">
                                  {Math.round(src.score * 100)}% match
                                </span>
                              )}
                              {src.category && (
                                <span className="px-1.5 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-500 uppercase text-[9px] font-semibold">
                                  {src.category}
                                </span>
                              )}
                            </div>
                          </div>
                          {src.title && src.filename && src.title !== src.filename && (
                            <div className="text-[10px] text-slate-500 mt-0.5">{src.title}</div>
                          )}
                          {src.snippet && (
                            <p className="text-[11px] text-slate-600 mt-1.5 pl-2 border-l-2 border-blue-200 italic">
                              “{src.snippet}”
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Human-in-the-Loop Ticket Preview & Confirmation Card (Module 9) */}
                {msg.pendingAction && (
                  <AgentTicketConfirmCard
                    pendingAction={msg.pendingAction}
                    onConfirm={(payload) => handleConfirmPendingTicket(msg.id, payload)}
                    onCancel={(confId) => handleCancelPendingTicket(msg.id, confId)}
                    onViewTicket={(ticketId) => navigate(`/tickets/${ticketId}`)}
                  />
                )}

                {/* Suggested Troubleshooting Actions & Ticket Creation */}
                {msg.actions && msg.actions.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-200/70 flex flex-wrap gap-2">
                    {msg.actions.map((act, i) => {
                      const isTicket = act.action_type === 'create_ticket';
                      return (
                        <button
                          key={i}
                          onClick={() => {
                            if (isTicket) {
                              handleOpenCreateTicket(msg);
                            } else {
                              navigate('/knowledge-base');
                            }
                          }}
                          className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-colors border ${
                            isTicket
                              ? 'bg-blue-600 hover:bg-blue-700 text-white border-blue-600 shadow-2xs'
                              : 'bg-white hover:bg-slate-100 text-slate-700 border-slate-200'
                          }`}
                        >
                          {isTicket ? (
                            <PlusCircle className="w-3.5 h-3.5" />
                          ) : (
                            <BookOpen className="w-3.5 h-3.5 text-blue-600" />
                          )}
                          <span>{act.label}</span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Follow-up Question Chips */}
                {msg.followUpQuestions && msg.followUpQuestions.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-200/70 space-y-1.5">
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
                      <MessageSquarePlus className="w-3 h-3 text-blue-600" />
                      Follow-up Questions
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.followUpQuestions.map((fq, idx) => (
                        <button
                          key={idx}
                          disabled={loading}
                          onClick={() => handleSend(fq)}
                          className="text-left text-[11px] px-2.5 py-1 rounded-full bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 hover:border-blue-300 transition-colors disabled:opacity-50"
                        >
                          {fq}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Resolved / Not Resolved Action Bar */}
                {msg.sender === 'agent' && !msg.isWelcome && !msg.isError && (
                  <div className="mt-3 pt-3 border-t border-slate-200/70 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                      Did this resolve your issue?
                    </span>
                    {msg.feedback === 'resolved' ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-lg">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Marked as Resolved
                      </span>
                    ) : msg.feedback === 'not_resolved' ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-lg">
                        <XCircle className="w-3.5 h-3.5" />
                        Not Resolved — Escalate via Ticket
                      </span>
                    ) : (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleFeedback(msg.id, 'resolved')}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 transition-colors"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Resolved
                        </button>
                        <button
                          onClick={() => handleFeedback(msg.id, 'not_resolved')}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 transition-colors"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          Not Resolved
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Timestamp */}
              <div
                className={`text-[10px] text-slate-400 px-1 ${
                  msg.sender === 'user' ? 'text-right' : 'text-left'
                }`}
              >
                {msg.timestamp}
              </div>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {loading && (
          <div className="flex items-start space-x-3">
            <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-slate-50 border border-slate-200/80 px-4 py-3 rounded-2xl rounded-tl-none">
              <div className="flex space-x-1.5 items-center h-4">
                <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" />
                <span className="text-[11px] text-slate-500 ml-2">
                  Searching Knowledge Base & consulting Groq LLM...
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompts Pills */}
      {messages.length <= 2 && (
        <div className="px-6 py-2 border-t border-slate-100 bg-slate-50/30 flex items-center space-x-2 overflow-x-auto">
          <Sparkles className="w-3.5 h-3.5 text-blue-600 shrink-0" />
          <span className="text-[11px] font-semibold text-slate-400 shrink-0 uppercase tracking-wider">
            Try Asking:
          </span>
          <div className="flex items-center space-x-2 shrink-0">
            {suggestedPrompts.map((prompt, i) => (
              <button
                key={i}
                onClick={() => handleSend(prompt)}
                className="text-[11px] px-2.5 py-1 bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50 text-slate-600 hover:text-blue-700 rounded-full transition-colors whitespace-nowrap"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Form */}
      <div className="p-4 border-t border-[#DCE4E3] bg-white transition-colors">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            placeholder="Ask a technical question or describe your IT issue..."
            className="flex-1 px-4 py-2.5 text-xs border border-[#DCE4E3] bg-white text-[#172B3A] placeholder-[#718096] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#087E8B] shadow-xs transition-colors"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="p-2.5 bg-[#087E8B] hover:bg-[#075C66] disabled:opacity-50 text-white rounded-xl shadow-xs transition-colors shrink-0"
            title="Send Message"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <div className="text-[10px] text-[#526773] text-center mt-2 flex items-center justify-center gap-1">
          <HelpCircle className="w-3 h-3 text-[#718096]" />
          <span>
            Answers retrieve verified company IT documents when available and clearly state when documentation is missing.
          </span>
        </div>
      </div>

      {/* Create Ticket Modal pre-filled from AI RAG conversation */}
      <CreateTicketModal
        isOpen={ticketModalOpen}
        onClose={() => {
          setTicketModalOpen(false);
          setTicketPrefill(null);
        }}
        onCreated={handleTicketCreated}
        initialData={ticketPrefill}
      />
    </div>
  );
};
