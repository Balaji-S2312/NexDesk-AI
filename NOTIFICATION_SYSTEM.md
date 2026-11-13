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
| `notification_type` | String(64) | `user_registered`, `ticket_submitted`, `new_incident_alert`, `high_priority_alert`, `ticket_assigned`, `ticket_status_updated`, `ticket_priority_updated`, `employee_reply`, `admin_comment`, `ticket_escalated`, `sla_approaching`, `sla_breached`, `ticket_resolved`, `ticket_resolved_confirmation`, `ticket_closed` |
| `event_key` | String(160) | Unique indexed idempotency key preventing duplicate notifications |
| `title` / `message` | String / Text | User-facing notification summary |
| `link` | String(255) | Relative frontend route (e.g. `/tickets/14`) |
| `is_read` | Boolean | Indexed read state |
| `created_at` / `read_at` | DateTime(UTC) | UTC timestamps |

### `ticket_comments` (`app/models/ticket.py`)
Persists bidirectional conversation entries (`ticket_id`, `author_id`, `author_role` in `{employee, admin}`, `message`, `created_at`). Access is restricted strictly to the ticket requester or administrators (`_get_accessible_ticket`).

### `email_delivery_logs` (`app/models/notification.py`)
Tracks outbound email reliability (`recipient_user_id`, `recipient_email`, `recipient_verified`, `ticket_id`, `event_type`, unique `event_key`, `subject`, `delivery_status` in `{sent, failed, skipped_unconfigured}`, `attempt_count`, sanitized `error_message`, `created_at`, `sent_at`). SMTP passwords are never persisted in DB logs.

### `users` Extension (`app/models/user.py`, `app/database/init_db.py`)
- `email_verified` (`Boolean`, default `False`) and `email_verified_at` (`DateTime(UTC)`), migrated idempotently on startup via `migrate_users_table()`.

---

## 3. Event Matrix & Recipient Routing

| Event | Employee Notification & Email | Administrator Notification & Email |
| :--- | :--- | :--- |
| **Event A: Ticket Submitted** | In-app `ticket_submitted` confirmation + background email to employee's DB email | In-app `new_incident_alert` + (`high_priority_alert` for High/Critical) + email to `ADMIN_NOTIFICATION_EMAIL` (`bb7578167@gmail.com`) |
| **Event B: Ticket Assigned** | In-app `ticket_assigned` + email showing assigned support group | In-app routing confirmation + Ticket History + email to `ADMIN_NOTIFICATION_EMAIL` |
| **Event C: Status / Priority Updated** | In-app `ticket_status_updated`, `ticket_priority_updated`, or `ticket_closed` + email | In-app alerts for priority escalations (`high_priority_alert`), closures (`ticket_closed`), or `pending`/`open` attention |
| **Event D: Comments & Replies** | In-app `admin_comment` + background email when an Admin comments | In-app `employee_reply` + background email when the Employee replies |
| **Event E: Registration, Escalation & SLA** | In-app `ticket_escalated` when escalated to human support | In-app alerts for `user_registered`, `ticket_escalated`, `sla_approaching`, and `sla_breached` (idempotent sync) |
| **Event F: Ticket Resolved** | In-app `ticket_resolved` + resolution email showing `resolution_notes` (never auto-closes) | In-app `ticket_resolved_confirmation` + email to `ADMIN_NOTIFICATION_EMAIL` |

---

## 4. Environment Configuration & Email Transport (HTTPS API + SMTP Fallback)

Add these environment variables in `backend/.env` (see `backend/.env.example`):

```dotenv
# Optional HTTPS Email Providers (port 443, prioritized over SMTP on PaaS hosts like Render)
RESEND_API_KEY=
BREVO_API_KEY=

# SMTP Configuration (used locally or on hosts allowing outbound TCP 25/465/587)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-smtp-app-password
SMTP_FROM_EMAIL=noreply@nexdesk.ai
SMTP_FROM_NAME=NexDesk AI
SMTP_USE_TLS=true
ADMIN_NOTIFICATION_EMAIL=bb7578167@gmail.com
ADMIN_EMAIL=bb7578167@gmail.com
FRONTEND_BASE_URL=http://localhost:5173
```

### Reliability & Security Guarantees
- **Non-blocking `BackgroundTasks` delivery:** Ticket commits and in-app notification inserts execute synchronously in the request transaction; email dispatch runs post-commit in FastAPI `BackgroundTasks` with a dedicated DB session so cloud SMTP latency never blocks HTTP responses or causes 15s frontend timeouts.
- **HTTPS API priority & production SMTP fail-fast:** When `RESEND_API_KEY` or `BREVO_API_KEY` is configured, emails dispatch over port `443` first. When `ENVIRONMENT=production` falls back to SMTP on hosts blocking ports `25/465/587`, `send_email()` fails fast after `1` attempt (`ENETUNREACH`/`EHOSTUNREACH` detection) without retry loops.
- **Recipient integrity:** Employee recipients are resolved exclusively from `User.email` on the backend; administrator alerts are read exclusively from centralized `ADMIN_NOTIFICATION_EMAIL`. Neither the frontend nor LLMs can override recipients.
- **HTML safety & live UI sync:** All dynamic fields in HTML email templates (`notification_templates.py`) are escaped via `html.escape()`; `NotificationBell` (10s polling + user-switch reset), `/notifications` (15s polling), and `TicketDetails` / `CreateTicketModal` synchronize via `nexdesk-notifications-updated`.

---

## 5. API Endpoints (`app/api/routes/notifications.py`, `tickets.py`, `auth.py`)
- `GET /api/notifications`: List authenticated user's notifications (`unread_only`, `ticket_id`, `limit`, `offset`); syncs admin SLA breach/approaching alerts automatically.
- `GET /api/notifications/unread-count`: Unread notification badge counter.
- `PATCH /api/notifications/{notification_id}/read`: Mark single notification read (enforces strict recipient ownership; returns `403` on foreign ID).
- `PATCH /api/notifications/read-all`: Mark all unread notifications for the authenticated user read.
- `GET /api/tickets/{ticket_id}/comments` & `POST /api/tickets/{ticket_id}/comments`: Scoped bidirectional comment thread triggering real-time employee/admin notifications.
- `GET /api/notifications/email-history`: Scoped email audit logs (employees see only their own records; admins see organizational records).
- `GET /api/notifications/config`: Admin-only sanitized SMTP, HTTPS provider (`https_provider_configured`, `email_transport`), & routing summary (never returns passwords or API keys).
- `POST /api/auth/confirm-email`: Authenticated self-service endpoint where an employee re-enters their registered email (trimmed whitespace, case-insensitive) to update their status from `Unconfirmed` to `User-confirmed` (`email_verified=True`, `email_verified_at`). Rejects mismatched emails with HTTP `400`.

---

## 6. Known Limitations
- **Render Free Tier Outbound SMTP Restriction:** Render Free Web Services block outbound TCP ports `25`, `465`, and `587` (`[Errno 101] Network is unreachable`). In-app notifications work 100% independently in PostgreSQL regardless of email transport; live external email delivery from Render requires setting `RESEND_API_KEY` or `BREVO_API_KEY` (port `443`) in Render environment variables.
- **In-app email confirmation vs. mailbox ownership:** Newly registered employees start with `email_verified=False` (`Unconfirmed`) and can mark their address as `User-confirmed` in-app on `/profile` (`POST /api/auth/confirm-email`). This is strictly a user-confirmed self-check and is not treated as proof of external mailbox ownership; ticket submission and login are never blocked by external email delivery.
