import {
  ImpactLevel,
  PriorityValue,
  StatusValue,
  TicketCategoryValue,
  UrgencyLevel,
} from '../types/ticket';

export interface Option<T extends string = string> {
  label: string;
  value: T;
}

export const CATEGORY_OPTIONS: Option<TicketCategoryValue>[] = [
  { label: 'Hardware', value: 'hardware' },
  { label: 'Software', value: 'software' },
  { label: 'Network', value: 'network' },
  { label: 'Access Management', value: 'access_management' },
  { label: 'Email', value: 'email' },
  { label: 'Security', value: 'security' },
  { label: 'Other', value: 'other' },
];

export const STATUS_OPTIONS: Option<StatusValue>[] = [
  { label: 'Open', value: 'open' },
  { label: 'Assigned', value: 'assigned' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Pending', value: 'pending' },
  { label: 'Resolved', value: 'resolved' },
  { label: 'Closed', value: 'closed' },
];

export const PRIORITY_OPTIONS: Option<PriorityValue>[] = [
  { label: 'P1 Critical', value: 'critical' },
  { label: 'P2 High', value: 'high' },
  { label: 'P3 Medium', value: 'medium' },
  { label: 'P4 Low', value: 'low' },
];

export const IMPACT_OPTIONS: Option<ImpactLevel>[] = [
  { label: 'High - many users / critical service', value: 'high' },
  { label: 'Medium - a team or important service', value: 'medium' },
  { label: 'Low - single user / minor service', value: 'low' },
];

export const URGENCY_OPTIONS: Option<UrgencyLevel>[] = [
  { label: 'High - work is blocked now', value: 'high' },
  { label: 'Medium - workaround exists', value: 'medium' },
  { label: 'Low - can wait', value: 'low' },
];

// Mirrors the backend ITIL impact x urgency matrix (backend remains the source of truth).
const MATRIX: Record<ImpactLevel, Record<UrgencyLevel, PriorityValue>> = {
  high: { high: 'critical', medium: 'high', low: 'medium' },
  medium: { high: 'high', medium: 'medium', low: 'low' },
  low: { high: 'medium', medium: 'low', low: 'low' },
};

export const previewPriority = (impact: ImpactLevel, urgency: UrgencyLevel): PriorityValue =>
  MATRIX[impact][urgency];

export const labelFor = (options: Option[], value: string | null | undefined): string =>
  options.find((o) => o.value === value)?.label ?? (value ?? '—');

export const priorityLabel = (p: PriorityValue): string => labelFor(PRIORITY_OPTIONS, p);

export const formatDateTime = (iso: string | null | undefined): string =>
  iso ? new Date(iso).toLocaleString() : '—';

export const FIELD_LABELS: Record<string, string> = {
  created: 'Ticket created',
  title: 'Title',
  description: 'Description',
  category: 'Category',
  subcategory: 'Subcategory',
  impact: 'Impact',
  urgency: 'Urgency',
  priority: 'Priority',
  status: 'Status',
  assigned_group: 'Assigned group',
  sla_deadline: 'SLA deadline',
  resolution_notes: 'Resolution notes',
};
