export interface AnalyticsSummary {
  total_tickets: number;
  open_tickets: number;
  in_progress_tickets: number;
  resolved_tickets: number;
  sla_breaches: number;
  avg_resolution_time_hours: number;
  avg_resolution_time_display: string;
  sla_compliance_rate: number;
  response_compliance_rate: number;
  resolution_compliance_rate: number;
  date_range: string;
  start_date: string | null;
  end_date: string | null;
}

export interface TicketTrendPoint {
  date: string;
  created: number;
  resolved: number;
  breached: number;
}

export interface CategoryDistributionItem {
  category: string;
  category_label: string;
  count: number;
  percentage: number;
}

export interface PriorityDistributionItem {
  priority: string;
  priority_label: string;
  count: number;
  percentage: number;
}

export interface StatusDistributionItem {
  status: string;
  status_label: string;
  count: number;
  percentage: number;
}

export interface WorkloadItem {
  group_id: number | null;
  group_name: string;
  total_tickets: number;
  open_tickets: number;
  breached_tickets: number;
}
