export interface NotificationItem {
  id: number;
  recipient_user_id: number;
  ticket_id?: number | null;
  ticket_number?: string | null;
  notification_type: string;
  title: string;
  message: string;
  link?: string | null;
  metadata?: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
  read_at?: string | null;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread_count: number;
}

export interface EmailDeliveryLogItem {
  id: number;
  recipient_user_id?: number | null;
  recipient_email: string;
  recipient_verified: boolean;
  ticket_id?: number | null;
  ticket_number?: string | null;
  event_type: string;
  subject: string;
  delivery_status: 'sent' | 'failed' | 'skipped_unconfigured' | string;
  attempt_count: number;
  error_message?: string | null;
  created_at: string;
  sent_at?: string | null;
}

export interface NotificationConfigStatus {
  admin_notification_email: string;
  smtp_configured: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_from_email: string;
  smtp_from_name: string;
  smtp_use_tls: boolean;
}
