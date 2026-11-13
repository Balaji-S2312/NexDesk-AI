import {
  ImpactLevel,
  PriorityValue,
  TicketCategoryValue,
  UrgencyLevel,
} from './ticket';

export interface IncidentClassificationResult {
  title: string;
  category: string;
  category_value: TicketCategoryValue;
  subcategory?: string | null;
  impact: string;
  impact_value: ImpactLevel;
  urgency: string;
  urgency_value: UrgencyLevel;
  recommended_priority: string;
  priority_label: string;
  priority_value: PriorityValue;
  assignment_group: string;
  summary: string;
  recommended_action: string;
  raw_llm_priority?: string;
  confidence_signals?: string;
}

export interface IncidentClassificationRequestPayload {
  description: string;
}
