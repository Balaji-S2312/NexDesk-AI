import axios, { AxiosError } from 'axios';
import { HealthResponse } from '../types/api';
import { AuthResponse, LoginCredentials, RegisterCredentials, User } from '../types/auth';
import { DashboardStatsResponse } from '../types/dashboard';
import {
  AssignmentGroup,
  Ticket,
  TicketCommentEntry,
  TicketCreatePayload,
  TicketHistoryEntry,
  TicketListResponse,
  TicketQuery,
  TicketUpdatePayload,
} from '../types/ticket';
import {
  KnowledgeDeleteResponse,
  KnowledgeDocument,
  KnowledgeDocumentDetail,
  KnowledgeDocumentListResponse,
  SemanticSearchResponse,
} from '../types/knowledge';
import {
  AnalyticsSummary,
  CategoryDistributionItem,
  PriorityDistributionItem,
  StatusDistributionItem,
  TicketTrendPoint,
  WorkloadItem,
} from '../types/analytics';
import {
  SLAOverview,
  SLAPolicy,
  SLAPolicyCreatePayload,
  SLAPolicyUpdatePayload,
} from '../types/sla';

const TOKEN_STORAGE_KEY = 'nexdesk_auth_token';
const DEFAULT_PROD_API_URL = 'https://nexdesk-backend-z98v.onrender.com/api';
const DEFAULT_DEV_API_URL = 'http://localhost:8000/api';

/**
 * Resolve the API base URL and guarantee a single `/api` suffix so deployed frontends
 * never send bare `/auth/login` or `/auth/register` requests or duplicate `/api/api`.
 */
export function resolveApiBaseUrl(rawUrl?: string): string {
  const fallback = import.meta.env.PROD ? DEFAULT_PROD_API_URL : DEFAULT_DEV_API_URL;
  const candidate = (rawUrl || '').trim();
  if (!candidate) {
    return fallback;
  }

  const normalized = candidate.replace(/\/+$/, '');
  if (!normalized || normalized === '/api' || /\/api$/i.test(normalized)) {
    return (normalized || fallback).replace(/(?:\/api)+$/i, '/api');
  }

  return `${normalized}/api`;
}

const resolvedBaseURL = resolveApiBaseUrl(
  import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL
);

const api = axios.create({
  baseURL: resolvedBaseURL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: inject scoped Bearer token and strip accidental duplicate /api/ prefixes
api.interceptors.request.use((config) => {
  if (config.url && config.url.startsWith('/api/') && resolvedBaseURL.endsWith('/api')) {
    config.url = config.url.slice(4);
  }
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: standardize error messages
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    let message = 'An unexpected error occurred while communicating with NexDesk API.';
    if (error.response?.data?.detail) {
      message = error.response.data.detail;
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      message = 'The request timed out while waiting for NexDesk backend. If generating an AI response, model inference may be taking longer than expected. Please retry.';
    } else if (error.response) {
      message = `Server error (${error.response.status}): ${error.message}`;
    } else if (error.request) {
      message = 'Unable to connect to NexDesk backend server. Please verify the backend service is running on port 8000.';
    }
    const apiError = new Error(message) as Error & { status?: number };
    apiError.status = error.response?.status;
    return Promise.reject(apiError);
  }
);

// Health check
export const getHealthApi = async (): Promise<HealthResponse> => {
  const response = await api.get<HealthResponse>('/health');
  return response.data;
};

export const checkBackendHealth = getHealthApi;

// Auth services
export const loginApi = async (credentials: LoginCredentials): Promise<AuthResponse> => {
  const response = await api.post<AuthResponse>('/auth/login', credentials);
  return response.data;
};

export const registerApi = async (credentials: RegisterCredentials): Promise<User> => {
  const response = await api.post<User>('/auth/register', credentials);
  return response.data;
};

export const getCurrentUserApi = async (): Promise<User> => {
  const response = await api.get<User>('/auth/me');
  return response.data;
};

export const getAdminUsersApi = async (): Promise<User[]> => {
  const response = await api.get<User[]>('/auth/users');
  return response.data;
};

export const getUsersApi = getAdminUsersApi;

// Dashboard Stats service
export const getDashboardStatsApi = async (): Promise<DashboardStatsResponse> => {
  const response = await api.get<DashboardStatsResponse>('/dashboard/stats');
  return response.data;
};

export const seedDemoTicketsApi = async (): Promise<{ message: string; count: number }> => {
  const response = await api.post<{ message: string; count: number }>('/dashboard/seed-demo-tickets');
  return response.data;
};

// Ticket services
export const createTicketApi = async (payload: TicketCreatePayload): Promise<Ticket> => {
  const response = await api.post<Ticket>('/tickets', payload);
  return response.data;
};

export const listTicketsApi = async (query: TicketQuery = {}): Promise<TicketListResponse> => {
  const params = Object.fromEntries(
    Object.entries(query).filter(([, v]) => v !== undefined && v !== '' && v !== null)
  );
  const response = await api.get<TicketListResponse>('/tickets', { params });
  return response.data;
};

export const getTicketApi = async (id: number): Promise<Ticket> => {
  const response = await api.get<Ticket>(`/tickets/${id}`);
  return response.data;
};

export const updateTicketApi = async (id: number, payload: TicketUpdatePayload): Promise<Ticket> => {
  const response = await api.patch<Ticket>(`/tickets/${id}`, payload);
  return response.data;
};

export const getTicketHistoryApi = async (id: number): Promise<TicketHistoryEntry[]> => {
  const response = await api.get<TicketHistoryEntry[]>(`/tickets/${id}/history`);
  return response.data;
};

export const listTicketCommentsApi = async (id: number): Promise<TicketCommentEntry[]> => {
  const response = await api.get<TicketCommentEntry[]>(`/tickets/${id}/comments`);
  return response.data;
};

export const addTicketCommentApi = async (id: number, message: string): Promise<TicketCommentEntry> => {
  const response = await api.post<TicketCommentEntry>(`/tickets/${id}/comments`, { message });
  return response.data;
};

export const listAssignmentGroupsApi = async (): Promise<AssignmentGroup[]> => {
  const response = await api.get<AssignmentGroup[]>('/assignment-groups');
  return response.data;
};

// AI Chatbot service
export interface ChatRequestPayload {
  conversation_id?: string | null;
  message: string;
}

export interface ChatSourceItem {
  id?: string;
  document_id?: number;
  filename?: string;
  title: string;
  page_number?: number;
  score?: number;
  category?: string;
  snippet?: string;
}

export interface ChatActionItem {
  action_type: string;
  label: string;
  payload?: Record<string, unknown>;
}

export interface ChatResponsePayload {
  conversation_id: string;
  response: string;
  sources: ChatSourceItem[];
  actions: ChatActionItem[];
  follow_up_questions?: string[];
  rag_used?: boolean;
  retrieved_chunks_count?: number;
  tool_calls?: AgentToolExecution[];
  pending_action?: PendingTicketAction | null;
}

export const sendChatMessageApi = async (payload: ChatRequestPayload): Promise<ChatResponsePayload> => {
  const response = await api.post<ChatResponsePayload>('/chat', payload, { timeout: 35000 });
  return response.data;
};

// Knowledge Base / RAG Ingestion services
export const uploadKnowledgeDocumentApi = async (
  file: File,
  category: string,
  title?: string
): Promise<KnowledgeDocument> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('category', category);
  if (title && title.trim()) {
    formData.append('title', title.trim());
  }
  const response = await api.post<KnowledgeDocument>('/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  return response.data;
};

export const listKnowledgeDocumentsApi = async (params?: {
  q?: string;
  category?: string;
  status?: string;
}): Promise<KnowledgeDocumentListResponse> => {
  const cleanParams = params
    ? Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== '' && v !== 'all'))
    : {};
  const response = await api.get<KnowledgeDocumentListResponse>('/knowledge/documents', {
    params: cleanParams,
  });
  return response.data;
};

export const getKnowledgeDocumentApi = async (id: number): Promise<KnowledgeDocumentDetail> => {
  const response = await api.get<KnowledgeDocumentDetail>(`/knowledge/documents/${id}`);
  return response.data;
};

export const deleteKnowledgeDocumentApi = async (id: number): Promise<KnowledgeDeleteResponse> => {
  const response = await api.delete<KnowledgeDeleteResponse>(`/knowledge/documents/${id}`);
  return response.data;
};

export const reprocessKnowledgeDocumentApi = async (id: number): Promise<KnowledgeDocument> => {
  const response = await api.post<KnowledgeDocument>(`/knowledge/documents/${id}/reprocess`, undefined, {
    timeout: 120000,
  });
  return response.data;
};

export const semanticSearchKnowledgeApi = async (params: {
  q: string;
  top_k?: number;
  category?: string;
  document_id?: number;
}): Promise<SemanticSearchResponse> => {
  const cleanParams = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== '' && v !== 'all')
  );
  const response = await api.get<SemanticSearchResponse>('/knowledge/search', {
    params: cleanParams,
    timeout: 60000,
  });
  return response.data;
};

// AI-Powered Incident Classification (Module 8)
import {
  IncidentClassificationRequestPayload,
  IncidentClassificationResult,
} from '../types/classification';
import {
  AdminOverridePayload,
  AgentConfirmPayload,
  AgentConfirmResponse,
  AgentEscalationRecord,
  AgentToolExecution,
  PendingTicketAction,
} from '../types/agent';
import {
  EmailDeliveryLogItem,
  NotificationConfigStatus,
  NotificationItem,
  NotificationListResponse,
} from '../types/notification';

export const classifyIncidentApi = async (
  payload: IncidentClassificationRequestPayload
): Promise<IncidentClassificationResult> => {
  const response = await api.post<IncidentClassificationResult>(
    '/classification/classify',
    payload,
    { timeout: 30000 }
  );
  return response.data;
};

// Agentic Workflow & Human-in-the-Loop Automation (Module 9)
export const prepareAgentTicketApi = async (payload: {
  description: string;
  conversation_id?: string | null;
  attempted_troubleshooting?: string[];
}): Promise<PendingTicketAction> => {
  const response = await api.post<PendingTicketAction>('/agent/prepare-ticket', payload);
  return response.data;
};

export const confirmAgentTicketApi = async (
  payload: AgentConfirmPayload
): Promise<AgentConfirmResponse> => {
  const response = await api.post<AgentConfirmResponse>('/agent/confirm', payload);
  return response.data;
};

export const cancelAgentTicketApi = async (confirmationId: string): Promise<{ confirmation_id: string; status: string }> => {
  const response = await api.post<{ confirmation_id: string; status: string }>('/agent/cancel', {
    confirmation_id: confirmationId,
  });
  return response.data;
};

export const escalateToHumanApi = async (payload: {
  reason: string;
  conversation_id?: string | null;
  ticket_id?: number;
  attempted_troubleshooting?: string[];
  recommended_group?: string;
}): Promise<AgentEscalationRecord> => {
  const response = await api.post<AgentEscalationRecord>('/agent/escalate', payload);
  return response.data;
};

export const listAgentEscalationsApi = async (params?: {
  ticket_id?: number;
  conversation_id?: number;
}): Promise<AgentEscalationRecord[]> => {
  const cleanParams = Object.fromEntries(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null)
  );
  const response = await api.get<AgentEscalationRecord[]>('/agent/escalations', {
    params: cleanParams,
  });
  return response.data;
};

export const overrideTicketRecommendationApi = async (
  ticketId: number,
  payload: AdminOverridePayload
): Promise<{ ticket: import('../types/ticket').Ticket; override_reason: string; changes_count: number }> => {
  const response = await api.post(`/agent/tickets/${ticketId}/override`, payload);
  return response.data;
};

// Enterprise Notifications & Email Delivery History (Module 9A)
export const listNotificationsApi = async (params?: {
  unread_only?: boolean;
  ticket_id?: number;
  limit?: number;
  offset?: number;
}): Promise<NotificationListResponse> => {
  const cleanParams = Object.fromEntries(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== false)
  );
  const response = await api.get<NotificationListResponse>('/notifications', { params: cleanParams });
  return response.data;
};

export const getUnreadNotificationCountApi = async (): Promise<{ unread_count: number }> => {
  const response = await api.get<{ unread_count: number }>('/notifications/unread-count');
  return response.data;
};

export const markNotificationReadApi = async (notificationId: number): Promise<NotificationItem> => {
  const response = await api.patch<NotificationItem>(`/notifications/${notificationId}/read`);
  return response.data;
};

export const markAllNotificationsReadApi = async (): Promise<{ marked_count: number }> => {
  const response = await api.patch<{ marked_count: number }>('/notifications/read-all');
  return response.data;
};

export const listEmailHistoryApi = async (params?: {
  ticket_id?: number;
  limit?: number;
}): Promise<EmailDeliveryLogItem[]> => {
  const cleanParams = Object.fromEntries(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null)
  );
  const response = await api.get<EmailDeliveryLogItem[]>('/notifications/email-history', { params: cleanParams });
  return response.data;
};

export const getNotificationConfigApi = async (): Promise<NotificationConfigStatus> => {
  const response = await api.get<NotificationConfigStatus>('/notifications/config');
  return response.data;
};

// In-app self-service email confirmation
export const confirmEmailApi = async (email: string): Promise<{ message: string; user: User }> => {
  const response = await api.post<{ message: string; user: User }>('/auth/confirm-email', { email });
  return response.data;
};

// Module 10: Service Analytics & SLA Management
export const getAnalyticsSummaryApi = async (
  range?: string,
  startDate?: string,
  endDate?: string
): Promise<AnalyticsSummary> => {
  const params: Record<string, string> = {};
  if (range) params.range = range;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const response = await api.get<AnalyticsSummary>('/analytics/summary', { params });
  return response.data;
};

export const getTicketTrendsApi = async (
  range?: string,
  startDate?: string,
  endDate?: string
): Promise<TicketTrendPoint[]> => {
  const params: Record<string, string> = {};
  if (range) params.range = range;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const response = await api.get<TicketTrendPoint[]>('/analytics/ticket-trends', { params });
  return response.data;
};

export const getCategoryDistributionApi = async (
  range?: string,
  startDate?: string,
  endDate?: string
): Promise<CategoryDistributionItem[]> => {
  const params: Record<string, string> = {};
  if (range) params.range = range;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const response = await api.get<CategoryDistributionItem[]>('/analytics/category-distribution', { params });
  return response.data;
};

export const getPriorityDistributionApi = async (
  range?: string,
  startDate?: string,
  endDate?: string
): Promise<PriorityDistributionItem[]> => {
  const params: Record<string, string> = {};
  if (range) params.range = range;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const response = await api.get<PriorityDistributionItem[]>('/analytics/priority-distribution', { params });
  return response.data;
};

export const getStatusDistributionApi = async (
  range?: string,
  startDate?: string,
  endDate?: string
): Promise<StatusDistributionItem[]> => {
  const params: Record<string, string> = {};
  if (range) params.range = range;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const response = await api.get<StatusDistributionItem[]>('/analytics/status-distribution', { params });
  return response.data;
};

export const getGroupWorkloadApi = async (
  range?: string,
  startDate?: string,
  endDate?: string
): Promise<WorkloadItem[]> => {
  const params: Record<string, string> = {};
  if (range) params.range = range;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const response = await api.get<WorkloadItem[]>('/analytics/workload', { params });
  return response.data;
};

export const getSLAOverviewApi = async (): Promise<SLAOverview> => {
  const response = await api.get<SLAOverview>('/sla/overview');
  return response.data;
};

export const listSLAPoliciesApi = async (): Promise<SLAPolicy[]> => {
  const response = await api.get<SLAPolicy[]>('/sla/policies');
  return response.data;
};

export const createSLAPolicyApi = async (payload: SLAPolicyCreatePayload): Promise<SLAPolicy> => {
  const response = await api.post<SLAPolicy>('/sla/policies', payload);
  return response.data;
};

export const updateSLAPolicyApi = async (
  policyId: number,
  payload: SLAPolicyUpdatePayload
): Promise<SLAPolicy> => {
  const response = await api.put<SLAPolicy>(`/sla/policies/${policyId}`, payload);
  return response.data;
};

export const deleteSLAPolicyApi = async (policyId: number): Promise<{ message: string }> => {
  const response = await api.delete<{ message: string }>(`/sla/policies/${policyId}`);
  return response.data;
};

export { TOKEN_STORAGE_KEY };
export default api;
