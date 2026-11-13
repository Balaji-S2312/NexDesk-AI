import { ImpactLevel, PriorityValue, Ticket, TicketCategoryValue, UrgencyLevel } from './ticket';

export interface AgentToolExecution {
  tool_name: string;
  status: string;
  summary: string;
  execution_ms: number;
  data?: Record<string, unknown> | null;
}

export interface PendingTicketAction {
  confirmation_id: string;
  action_type: string;
  status: 'pending_confirmation' | 'confirmed' | 'cancelled' | string;
  conversation_id?: string | null;
  title: string;
  description: string;
  category: string;
  category_value: TicketCategoryValue;
  subcategory?: string | null;
  impact: string;
  impact_value: ImpactLevel;
  urgency: string;
  urgency_value: UrgencyLevel;
  recommended_priority: string;
  priority_label: string;
  assignment_group: string;
  group_id?: number | null;
  summary: string;
  recommended_action: string;
  attempted_troubleshooting: string[];
  retrieved_sources: Array<Record<string, unknown>>;
  escalation_summary?: string | null;
  created_ticket_id?: number | null;
  created_ticket_number?: string | null;
}

export interface AgentConfirmPayload {
  confirmation_id: string;
  title?: string;
  description?: string;
  category?: TicketCategoryValue;
  subcategory?: string;
  impact?: ImpactLevel;
  urgency?: UrgencyLevel;
  assignment_group?: string;
  escalate_to_human?: boolean;
}

export interface AgentEscalationRecord {
  id: number;
  ticket_id?: number | null;
  ticket_number?: string | null;
  conversation_id?: number | null;
  user_id: number;
  user_name?: string | null;
  recommended_group_id?: number | null;
  recommended_group_name: string;
  escalation_summary: string;
  attempted_troubleshooting: string[];
  relevant_conversation?: string | null;
  retrieved_references: Array<{
    filename?: string;
    title?: string;
    page_number?: number;
    score?: number;
  }>;
  status: string;
  created_at: string;
}

export interface AgentConfirmResponse {
  confirmation_id: string;
  status: string;
  ticket: Ticket;
  escalation?: AgentEscalationRecord | null;
  tool_calls: AgentToolExecution[];
  message: string;
}

export interface AdminOverridePayload {
  category?: TicketCategoryValue;
  subcategory?: string;
  impact?: ImpactLevel;
  urgency?: UrgencyLevel;
  group_id?: number;
  assignment_group?: string;
  status?: string;
  override_reason: string;
}

export type PriorityPreview = PriorityValue;
