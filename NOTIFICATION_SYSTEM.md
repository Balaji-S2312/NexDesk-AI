# NexDesk AI – Enterprise Notification, Email Communication & Ticket Event System (Module 9A)

## 1. Overview
Module 9A adds a centralized, event-driven notification and outbound SMTP email communication pipeline to NexDesk AI. Every ticket lifecycle event automatically emits idempotent in-app notifications scoped to authorized recipients and logs outbound HTML/plain-text email dispatches without blocking core ITSM transactions.

---

## 2. Database Schema

### `notifications` (`app/models/notification.py`)
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Primary key |
| `recipient_user_id` | Integer (FK → `users.id`) | Indexed, cascades on user delete; strictly scoped to recipient |
| `ticket_id` | Integer (FK → `tickets.id`) | Indexed, cascades on ticket delete |
| `ticket_number` | String(20) | Indexed ticket code (e.g. `INC0000014`) |
| `notification_type` | String(64) | `ticket_submitted`, `new_incident_alert`, `ticket_assigned`, `ticket_status_updated`, `ticket_resolved`, `ticket_resolved_confirmation`, `ticket_closed` |
| `event_key` | String(160) | Unique indexed idempotency key preventing duplicate notifications |
| `title` / `message` | String / Text | User-facing notification summary |
| `link` | String(255) | Relative frontend route (e.g. `/tickets/14`) |
| `is_read` | Boolean | Indexed read state |
| `created_at` / `read_at` | DateTime(UTC) | UTC timestamps |

### `email_delivery_logs` (`app/models/notification.py`)
Tracks outbound email reliability (`recipient_user_id`, `recipient_email`, `recipient_verified`, `ticket_id`, `event_type`, unique `event_key`, `subject`, `delivery_status` in `{sent, failed, skipped_unconfigured}`, `attempt_count`, sanitized `error_message`, `created_at`, `sent_at`). SMTP passwords are never persisted in DB logs.

### `users` Extension (`app/models/user.py`, `app/database/init_db.py`)
- `email_verified` (`Boolean`, default `False`) and `email_verified_at` (`DateTime(UTC)`), migrated idempotently on startup via `migrate_users_table()`.

---

## 3. Event Matrix & Recipient Routing

| Event | Employee Notification & Email | Administrator Notification & Email |
| :--- | :--- | :--- |
| **Event A: Ticket Submitted** | In-app confirmation + email to authenticated employee's DB email (`ticket_number`, title, status, timestamp) | In-app `new_incident_alert` + email to `ADMIN_NOTIFICATION_EMAIL` (`bb7578167@gmail.com`) with ticket ID, employee name, category, priority, ticket link |
| **Event B: Ticket Assigned** | In-app + email showing assigned support group and ticket status | In-app routing confirmation + Ticket History + email to `ADMIN_NOTIFICATION_EMAIL` |
| **Event C: Ticket Status Updated** | In-app + email for meaningful status changes (`open`, `assigned`, `in_progress`, `pending`, `closed`). Minor non-status edits do not trigger emails. | Dashboard status visibility (+ notification when requester closes a resolved ticket) |
| **Event D: Ticket Resolved** | In-app + resolution email showing `resolution_notes`, `ticket_number`, timestamp, and ticket link (never auto-closes) | In-app `ticket_resolved_confirmation` + email to `ADMIN_NOTIFICATION_EMAIL` |

---

## 4. Environment Configuration & SMTP Setup

Add these environment variables in `backend/.env` (see `backend/.env.example`):

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-smtp-app-password
SMTP_FROM_EMAIL=noreply@nexdesk.ai
SMTP_FROM_NAME=NexDesk AI
SMTP_USE_TLS=true
ADMIN_NOTIFICATION_EMAIL=bb7578167@gmail.com
FRONTEND_BASE_URL=http://localhost:5173
```

### Reliability & Security Guarantees
- **Non-blocking delivery:** Ticket commits succeed first. SMTP failures trigger controlled retries (`SMTP_MAX_RETRIES=2`), log sanitized error details (`[REDACTED]` for credentials), and never roll back ticket operations.
- **Unconfigured SMTP fallback:** When `SMTP_HOST` is blank, in-app notifications still run normally and emails log `skipped_unconfigured` rather than falsely claiming delivery.
- **Recipient integrity:** Employee recipients are resolved exclusively from `User.email` on the backend; administrator alerts are read exclusively from `ADMIN_NOTIFICATION_EMAIL`. Neither the frontend nor LLMs can override recipients.
- **HTML safety:** All dynamic fields in HTML email templates (`notification_templates.py`) are escaped via `html.escape()`, and subjects omit sensitive ticket descriptions.

---

## 5. API Endpoints (`app/api/routes/notifications.py`, `auth.py`)
- `GET /api/notifications`: List authenticated user's notifications (`unread_only`, `ticket_id`, `limit`, `offset`).
- `GET /api/notifications/unread-count`: Unread notification badge counter.
- `PATCH /api/notifications/{notification_id}/read`: Mark single notification read (enforces strict recipient ownership; returns `403` on foreign ID).
- `PATCH /api/notifications/read-all`: Mark all unread notifications for the authenticated user read.
- `GET /api/notifications/email-history`: Scoped email audit logs (employees see only their own records; admins see organizational records).
- `GET /api/notifications/config`: Admin-only sanitized SMTP & routing summary (never returns `SMTP_PASSWORD`).
- `POST /api/auth/confirm-email`: Authenticated self-service endpoint where an employee re-enters their registered email (trimmed whitespace, case-insensitive) to update their status from `Unconfirmed` to `User-confirmed` (`email_verified=True`, `email_verified_at`). Rejects mismatched emails with HTTP `400`.

---

## 6. Known Limitations
- **In-app email confirmation vs. mailbox ownership:** Newly registered employees start with `email_verified=False` (`Unconfirmed`) and can mark their address as `User-confirmed` in-app on `/profile` (`POST /api/auth/confirm-email`). This is strictly a user-confirmed self-check and is not treated as proof of external mailbox ownership; ticket submission and login are never blocked by external email delivery.
- **Live external SMTP test:** Ticket, assignment, resolution, and admin alerts remain separate optional email functionality (`smtplib.SMTP` mocked in `test_notifications.py` & `test_email_verification_notifications.py`); real external inbox delivery requires configuring live `SMTP_*` credentials in `backend/.env` on a host permitting outbound SMTP.
