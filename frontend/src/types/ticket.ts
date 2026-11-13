export type TicketCategoryValue =
  | 'hardware'
  | 'software'
  | 'network'
  | 'access_management'
  | 'email'
  | 'security'
  | 'other';
export type ImpactLevel = 'high' | 'medium' | 'low';
export type UrgencyLevel = 'high' | 'medium' | 'low';
export type PriorityValue = 'critical' | 'high' | 'medium' | 'low';
export type StatusValue = 'open' | 'assigned' | 'in_progress' | 'pending' | 'resolved' | 'closed';

export interface Ticket {
  id: number;
  ticket_number: string;
  title: string;
  description: string;
  category: TicketCategoryValue;
  subcategory: string | null;
  impact: ImpactLevel;
  urgency: UrgencyLevel;
  priority: PriorityValue;
  priority_label: string;
  status: StatusValue;
  group_id: number | null;
  assigned_group: string | null;
  requester_id: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  response_deadline?: string | null;
  sla_deadline: string | null;
  first_responded_at?: string | null;
  sla_breached: boolean;
  response_breached?: boolean;
  resolution_breached?: boolean;
  is_overdue?: boolean;
  is_near_breach?: boolean;
  sla_status?: string;
  ticket_age_hours?: number;
  ticket_age_display?: string;
  resolution_notes: string | null;
  resolved_at: string | null;
}

export interface TicketListResponse {
  items: Ticket[];
  total: number;
  page: number;
  page_size: number;
}

export interface TicketHistoryEntry {
  id: number;
  ticket_id: number;
  field_changed: string;
  old_value: string | null;
  new_value: string | null;
  changed_by: string | null;
  changed_by_id: number | null;
  created_at: string;
}

export interface TicketCreatePayload {
  title: string;
  description: string;
  category: TicketCategoryValue;
  subcategory?: string;
  impact: ImpactLevel;
  urgency: UrgencyLevel;
}

export interface TicketUpdatePayload {
  title?: string;
  description?: string;
  category?: TicketCategoryValue;
  subcategory?: string | null;
  impact?: ImpactLevel;
  urgency?: UrgencyLevel;
  status?: StatusValue;
  group_id?: number | null;
  resolution_notes?: string | null;
}

export interface TicketQuery {
  q?: string;
  status?: string;
  priority?: string;
  category?: string;
  group_id?: number;
  page?: number;
  page_size?: number;
}

export interface AssignmentGroup {
  id: number;
  name: string;
  description: string | null;
}
