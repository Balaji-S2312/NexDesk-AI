export interface SLAPolicy {
  id: number;
  name: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  response_time_minutes: number;
  response_time_hours: number | null;
  resolution_time_hours: number;
  business_hours_only: boolean;
  escalation_contact: string | null;
  created_at?: string;
}

export interface SLAPolicyCreatePayload {
  name: string;
  priority: string;
  response_time_minutes: number;
  response_time_hours?: number;
  resolution_time_hours: number;
  business_hours_only: boolean;
  escalation_contact?: string;
}

export interface SLAPolicyUpdatePayload {
  name?: string;
  response_time_minutes?: number;
  response_time_hours?: number;
  resolution_time_hours?: number;
  business_hours_only?: boolean;
  escalation_contact?: string;
}

export interface SLAPolicyMetrics {
  policy: SLAPolicy;
  active_tickets: number;
  resolved_tickets: number;
  breached_tickets: number;
  compliance_rate: number;
}

export interface SLAIncidentItem {
  id: number;
  ticket_number: string;
  title: string;
  priority: string;
  priority_label: string;
  status: string;
  assigned_group: string | null;
  created_by: string | null;
  created_at: string;
  response_deadline: string | null;
  resolution_deadline: string | null;
  first_responded_at: string | null;
  resolved_at: string | null;
  response_breached: boolean;
  resolution_breached: boolean;
  is_overdue: boolean;
  is_near_breach: boolean;
  sla_status: string;
  ticket_age_display: string;
}

export interface SLAOverview {
  total_evaluated: number;
  total_breached: number;
  total_overdue: number;
  overall_compliance_rate: number;
  response_compliance_rate: number;
  resolution_compliance_rate: number;
  policies: SLAPolicyMetrics[];
  overdue_incidents: SLAIncidentItem[];
  recent_breaches: SLAIncidentItem[];
}
