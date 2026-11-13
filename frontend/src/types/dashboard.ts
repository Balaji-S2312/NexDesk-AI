export type TicketStatus = 'open' | 'assigned' | 'in_progress' | 'pending' | 'resolved' | 'closed';
export type TicketPriority = 'low' | 'medium' | 'high' | 'critical';
export type TicketCategory = 'hardware' | 'software' | 'network' | 'access_management' | 'email' | 'security' | 'other';

export interface TicketItem {
  id: number;
  ticket_number?: string;
  title: string;
  description?: string;
  status: TicketStatus;
  priority: TicketPriority;
  priority_label?: string;
  category: string;
  assigned_group?: string | null;
  requester?: string;
  assignee?: string;
  created_at: string;
  updated_at?: string;
  resolved_at?: string | null;
  resolution_notes?: string | null;
}

export interface ActivityItem {
  id: number;
  action: string;
  resource_type: string;
  details?: string;
  created_at: string;
}

export interface PriorityDistribution {
  priority: string;
  count: number;
  color: string;
}

export interface CategoryDistribution {
  category: string;
  count: number;
}

export interface IncidentTrend {
  date: string;
  incidents: number;
  resolved: number;
}

export interface AdminMetrics {
  total_incidents: number;
  open_incidents: number;
  in_progress_incidents: number;
  resolved_incidents: number;
  sla_breaches: number;
  average_resolution_hours: number;
}

export interface EmployeeMetrics {
  total_tickets: number;
  open_tickets: number;
  resolved_tickets: number;
}

export interface AdminDashboardData {
  role: 'admin';
  is_development_baseline: boolean;
  metrics: AdminMetrics;
  priority_distribution: PriorityDistribution[];
  category_distribution: CategoryDistribution[];
  incident_trends: IncidentTrend[];
  recent_incidents: TicketItem[];
  recently_assigned_incidents?: TicketItem[];
  recently_resolved_incidents?: TicketItem[];
  recent_notifications?: import('./notification').NotificationItem[];
}

export interface EmployeeDashboardData {
  role: 'employee';
  is_development_baseline: boolean;
  metrics: EmployeeMetrics;
  recent_tickets: TicketItem[];
  recent_activity: ActivityItem[];
}

export type DashboardStatsResponse = AdminDashboardData | EmployeeDashboardData;

export interface AssignmentGroupItem {
  id: number;
  name: string;
  description: string;
  members_count: number;
  lead: string;
  created_at: string;
}

export interface SLAPolicyItem {
  id: number;
  name: string;
  priority: TicketPriority;
  response_time_hours: number;
  resolution_time_hours: number;
  compliance_rate: number;
}

export interface AuditLogItem {
  id: number;
  action: string;
  resource_type: string;
  resource_id?: string;
  details?: string;
  ip_address?: string;
  user_email?: string;
  created_at: string;
}
