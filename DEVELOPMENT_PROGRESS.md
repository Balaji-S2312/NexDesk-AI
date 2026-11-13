# NexDesk AI â€“ Development Progress Tracker

## Project Overview
NexDesk AI is an Agentic Generative AI-powered IT Service Management (ITSM) platform built to automate IT incident triage, intelligent ticket categorization, automated resolution synthesis, vector-based runbook retrieval, and real-time SLA management.

---

## Module Status Overview

| Module | Title | Status | Completion Date |
| :--- | :--- | :--- | :--- |
| **Module 1** | Project Initialization & System Architecture | **COMPLETED** | 2026-11-12 |
| **Module 2** | Database and Authentication | **COMPLETED** | 2026-11-12 |
| **Module 3** | Enterprise Frontend and Dashboard | **COMPLETED** | 2026-11-12 |
| **Module 4** | Incident and Ticket Management | **COMPLETED** | 2026-11-12 |
| **Module 5** | Groq LLM Integration and AI Service | **COMPLETED** | 2026-11-12 |
| **Module 6** | RAG Document Ingestion and Vector Storage | **COMPLETED** | 2026-11-13 |
| **Module 7** | Retrieval-Augmented Generation Integration | **COMPLETED** | 2026-11-13 |
| **Module 8** | AI-Powered Incident Classification | **COMPLETED** | 2026-11-13 |
| **Module 9** | Agentic AI Workflow and Human-in-the-Loop Automation | **COMPLETED** | 2026-11-13 |
| **Module 9A** | Enterprise Notification, Email Communication & Ticket Event System | **COMPLETED** | 2026-11-13 |
| **Module 10** | SLA Management and Service Analytics | **COMPLETED** | 2026-11-13 |
| **Module 11** | End-to-End Integration, QA & Verification | **COMPLETED** | 2026-11-13 |
| **Module 12A** | Global Contrast & Enterprise Light UI System (Deep Teal) | **COMPLETED** | 2026-11-13 |
| **Module 12B** | Email Verification & Automated Gmail SMTP Notifications | **COMPLETED** | 2026-11-13 |
| **Module 13** | Cloud Deployment, Production Hardening & Live Cloud Launch | **COMPLETED & LIVE** | 2026-11-13 |

---

## Module 2 Checklist: Database and Authentication

- [x] **SQLite & SQLAlchemy 2.0 Integration:** Safe session lifecycle management with automatic rollback and UTC timestamps.
- [x] **9 Core Relational Models Implemented:**
  - `User` (id, name, email, password_hash, role ['employee', 'admin'], created_at, updated_at).
  - `Ticket` (title, description, status, priority, category, foreign keys to requester, assignee, group, sla_policy).
  - `Conversation` (ticket_id, user_id, 1-to-many relationship with messages).
  - `Message` (conversation_id, sender_type ['user', 'agent', 'system'], sender_id, content).
  - `Document` (title, content, file_path, file_type, category, created_by_id).
  - `TicketHistory` (ticket_id, user_id, field_changed, old_value, new_value, audit timestamp).
  - `AssignmentGroup` (name, description, relations to tickets).
  - `SLAPolicy` (name, priority, response_time_hours, resolution_time_hours, relations to tickets).
  - `AuditLog` (user_id, action, resource_type, resource_id, details, ip_address, timestamp).
- [x] **Database Initialization & Seeding:**
  - Automated table provisioning on startup (`Base.metadata.create_all`).
  - Seeded Demo Admin: `admin@nexdesk.ai` / `AdminPassword123!` (role: `admin`).
  - Seeded Demo Employee: `employee@nexdesk.ai` / `EmployeePassword123!` (role: `employee`).
  - Default SLA policies (Critical, High, Medium, Low) and default Assignment Groups.
- [x] **Authentication Endpoints:**
  - `POST /api/auth/register` (strictly enforces `role="employee"`, prevents unauthorized privilege escalation).
  - `POST /api/auth/login` (verifies bcrypt hash, returns signed JWT access token).
  - `GET /api/auth/me` (protected route returning current authenticated user profile).
  - `GET /api/auth/users` (administrative route restricted to users with `role="admin"`).
- [x] **Security Guarantees:**
  - Passwords hashed using salted Bcrypt (`bcrypt.hashpw`).
  - Passwords and password hashes never exposed in responses (`UserResponse`).
  - Strict role-based access control (RBAC) enforced on FastAPI route dependencies.
  - Employees blocked from accessing organization administrative endpoints (`403 Forbidden`).
- [x] **Frontend Authentication System:**
  - Login Page (`/login`) with demo credential auto-fill buttons.
  - Registration Page (`/register`) with client validation and RBAC safeguards.
  - Authentication Context (`AuthContext` & `useAuth` hook) managing token persistence.
  - Protected Route Component (`ProtectedRoute`) with role-based routing checks.
  - Logout functionality with state reset and token eviction.
- [x] **Quality & Test Verification:**
  - Backend Unit & Integration Tests: **8 passed in 2.53s** (`backend/tests/`).
  - Frontend Build (`tsc && vite build`): **Built cleanly in 6.02s**.
  - Frontend Linting (`eslint`): **0 errors, 0 warnings**.
  - Live End-to-End API verification completed across all acceptance criteria.


---

## Module 3 Checklist: Enterprise Frontend and Dashboard

- [x] **Enterprise SaaS Design System:**
  - Professional light theme with white and light-grey backgrounds (`bg-slate-50`, `bg-white`).
  - Navy typography (`text-slate-900`, `text-slate-800`).
  - Professional blue primary accents (`#2563eb` / `blue-600`), subtle shadows, rounded cards, minimal glassmorphism.
  - Zero clutter, clean tables, consistent spacing, fully responsive layout.
- [x] **Reusable Component Library:**
  - `Sidebar` (collapsible, mobile responsive drawer, role-aware navigation).
  - `TopNavbar` (sticky top header, real-time backend health badge, notifications, user avatar).
  - `KPICard` (support for title, value, subtitle, custom icons, loading skeletons, accent color palettes).
  - `DataTable` (generic type-safe sortable columns, paginated, loading skeleton, custom empty state).
  - `StatusBadge` & `PriorityBadge` (standardized ITSM color tokens).
  - `SearchBar` & `FilterPanel` (multi-select filter bars, clear button).
  - `Modal` & `ConfirmationDialog` (accessible dialogs with backdrop blur).
  - `ToastContext` & `useToast` (global toast notification system).
  - `LoadingSkeleton` & `EmptyState`.
- [x] **Employee Experience:**
  - `EmployeeOverview` (welcome banner, 3 KPI cards, quick actions, recent tickets table, activity timeline, new ticket modal).
  - `AISupport` (interactive AI troubleshooting chat with simulated automated runbook guidance).
  - `MyTickets` (filter panel, search bar, sortable data table, ticket creation modal).
  - `KnowledgeBase` (searchable IT runbooks with category filtering and article reader modal).
  - `Profile` (user credentials, active session status, sign-out).
- [x] **Admin Command Center:**
  - `AdminDashboard` (6 KPI metrics connected to real DB, Recharts 7-day AreaChart trend, Severity PieChart, Category BarChart, organization incidents table, demo seed trigger).
  - `AdminIncidents` (enterprise triage queue with filter panel, status transition, resolve confirmation dialog).
  - `AdminAssignmentGroups` (ITSM routing matrix, group directory, live user roster from DB).
  - `AdminSLAManagement` (P1-P4 SLA rules, response/resolution targets, escalation paths).
  - `AdminAuditLogs` (compliance audit trail with actor, action, origin IP, result).
  - `AdminSettings` (Groq model selection, JWT expiry, SLA breach automation).
- [x] **Backend Dashboard API Integration:**
  - `GET /api/dashboard/stats` delivering real role-scoped metrics directly from SQLite database.
  - `POST /api/dashboard/seed-demo-tickets` for on-demand test data loading.
  - No hardcoded metrics: baseline indicators shown when database has no tickets.
- [x] **Verification:**
  - Frontend Linting: **0 errors, 0 warnings** (`npm run lint`).
  - Frontend Build: **TypeScript strict compiled cleanly in 8.9s** (`npm run build`).
  - Backend Tests: **10 passed in 2.95s** (`pytest -v`).
  - Servers running and live: FastAPI on `http://127.0.0.1:8000` & Vite on `http://localhost:5173`.



---

## Module 4 Checklist: Incident and Ticket Management

- [x] Ticket model extended (ticket number, subcategory, impact, urgency, SLA deadline, resolution notes, resolved_at) with an idempotent in-place migration for existing databases.
- [x] ITIL impact × urgency matrix → P1–P4 priority; SLA deadline from SLA policy; unique `INCnnnnnnn` numbers.
- [x] Endpoints: `POST/GET /api/tickets`, `GET/PATCH /api/tickets/{id}`, `GET /api/tickets/{id}/history`, `GET /api/assignment-groups`.
- [x] Employee ownership enforced (own tickets only, foreign → 404; may only close own resolved ticket). Admin full access.
- [x] Per-field history (old/new value, actor, timestamp) and audit-log entries on create/update.
- [x] Search, status/priority/category/group filters, pagination.
- [x] Frontend: My Tickets, All Incidents, Create Ticket modal, Ticket Details with status/group update and history timeline.
- [x] Dashboard metrics now derived from real ticket data (average resolution time and SLA breaches are computed, no longer placeholders); demo seeding is admin-only and goes through the real workflow.
- [x] Verification: backend **42 tests passed**, frontend lint 0 warnings, `tsc && vite build` OK, live API smoke test OK.



---

## Module 5 Checklist: Groq LLM Integration and AI Service

- [x] **LLM Client & Provider Configuration:**
  - Secure integration with Groq API endpoint (`https://api.groq.com/openai/v1/chat/completions`).
  - Active model support: `openai/gpt-oss-120b` (supported and verified against Groq API).
  - API credentials stored exclusively in backend `.env` (`GROQ_API_KEY`, `GROQ_MODEL`) and never exposed to the frontend.
  - Safe sanitized logging masking credential secrets.
- [x] **Backend Architecture (`services/llm/`):**
  - `groq_client.py`: Async HTTP client with connection timeouts (30s), rate-limit handling, retry abstractions, and authentication error protection.
  - `prompt_manager.py`: Enterprise IT Support persona with anti-fabrication guidelines and context assembly.
  - `response_handler.py`: Response validation, token cleaning, knowledge source extraction, and contextual action generation.
  - `schemas.py`: Pydantic V2 schemas for request validation, structured output, action buttons, and source citations.
- [x] **Central Chat API (`POST /api/chat`):**
  - JWT Bearer protected endpoint.
  - Relational database persistence for conversations and message turns (`conversations`, `messages`).
  - Full conversational context continuity across multi-turn exchanges.
  - Graceful degradation: descriptive notice returned when API key is unconfigured without server crashing.
- [x] **Frontend Experience (`AISupport.tsx`):**
  - Full enterprise chat UI with user/AI avatars, styled bubbles, and auto-scrolling.
  - Animated typing indicator ("Consulting Groq LLM...").
  - Suggested inquiry prompt pills.
  - Source reference cards embedded under AI answers.
  - Action buttons triggering instant incident ticket creation via `CreateTicketModal`.
  - Conversation reset ("New Chat") functionality.
- [x] **Verification & Test Suite:**
  - Backend pytest suite: **47 passed in 15.01s** (`backend/tests/test_chat.py` + full regression).
  - Frontend TypeScript build & ESLint: **0 errors, 0 warnings**.
  - Live Groq API end-to-end conversation verified against real backend.


---

## Module 6 Checklist: RAG Document Ingestion and Vector Storage

- [x] **Document Extraction & Normalization (`services/rag/extractor.py`):**
  - PDF extraction via **PyMuPDF** (`fitz`) preserving 1-based page numbers.
  - Word extraction via **python-docx** and plain text (`.txt`) extraction with UTF-8 / latin-1 fallback and form-feed page splitting.
  - File extension, payload validation, size guard (`MAX_UPLOAD_SIZE_MB=15`), and text normalization.
- [x] **Token-Aware Chunking (`services/rag/chunker.py`):**
  - ~500 tokens per chunk with ~75 tokens overlap preserving `page_number` per chunk across sentence and word boundaries.
- [x] **Singleton Embeddings (`services/rag/embeddings.py`):**
  - Thread-safe `EmbeddingService` loading `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) once and reusing across requests.
- [x] **Persistent ChromaDB Vector Store (`services/rag/vector_store.py`):**
  - Persistent storage (`./chroma_db`, collection `nexdesk_knowledge`, cosine similarity) storing `chunk_id`, `document_id`, `text`, `embedding`, `source_filename`, `page_number`, `title`, `category`, and `token_count`.
- [x] **SQLite Metadata & Deduplication (`models/document.py`, `database/init_db.py`, `services/rag/pipeline.py`):**
  - Extended `Document` model (`filename`, `file_size`, `file_hash`, `status`, `error_message`, `page_count`, `chunk_count`) with idempotent `migrate_documents_table()`.
  - SHA-256 duplicate file detection (`409 Conflict`) and compliance `AuditLog` entries for upload, reprocess, and delete.
- [x] **Knowledge Base API (`api/routes/knowledge.py`) & Frontend (`KnowledgeBase.tsx`):**
  - Endpoints: `POST /api/knowledge/upload` (admin only), `GET /api/knowledge/documents`, `GET /api/knowledge/documents/{id}`, `POST /api/knowledge/documents/{id}/reprocess` (admin only), `DELETE /api/knowledge/documents/{id}` (admin only), `GET /api/knowledge/search`.
  - Frontend integrated with real SQLite + ChromaDB APIs for upload, filename filtering, semantic search with page citations & match scores, document inspection modal, reprocessing, and deletion.
- [x] **Verification:**
  - Backend pytest suite: **51 passed in 19.13s** (`tests/test_knowledge.py` + full Modules 1–6 regression).
  - Frontend ESLint & TypeScript build: **0 errors, 0 warnings** (`npm run lint`, `npm run build`).
  - Live HTTP multipart PDF upload, semantic search, UI reprocessing, UI deletion, and Employee RBAC view verified end-to-end.


---

## Module 7 Checklist: Retrieval-Augmented Generation Integration

- [x] **Vector Retrieval & Thresholding (`services/rag/retriever.py`, `core/config.py`):**
  - End-to-end `retrieve_relevant_context()` embedding queries with `all-MiniLM-L6-v2`, searching ChromaDB (`RAG_TOP_K=5`), filtering by cosine similarity (`RAG_RELEVANCE_THRESHOLD=0.28`), and constructing bounded `<retrieved_documents>` context (`RAG_MAX_CONTEXT_CHARS=6000`).
- [x] **RAG Prompt Hardening (`services/llm/prompt_manager.py`):**
  - Enforces grounded answers with filename + page citations, honest disclosure when KB lacks matching docs, and untrusted-data boundaries around retrieved excerpts to resist prompt injection.
- [x] **Real Source Attribution & Structured Outputs (`services/llm/response_handler.py`, `services/llm/schemas.py`, `api/routes/chat.py`):**
  - Replaced placeholder runbook matching with real ChromaDB chunk attribution (`filename`, `page_number`, `score`, `snippet`), category-prefilled `create_ticket` actions, `suggested_step` actions, `follow_up_questions`, and `rag_used` / `retrieved_chunks_count` flags.
  - Added multi-turn query augmentation for short follow-up turns.
- [x] **AI Support Chat UI (`frontend/src/pages/AISupport.tsx`, `CreateTicketModal.tsx`, `services/api.ts`):**
  - Retrieved Document Indicator badges (`Grounded in N retrieved KB source(s)` vs `No matching KB documentation found above threshold`).
  - Knowledge Source Cards with filename, Page N, relevance % badge, category, and chunk excerpt.
  - Follow-up Question chips, Suggested Actions, interactive `Resolved` / `Not Resolved` buttons, and pre-filled `CreateTicketModal` ticket escalation.
- [x] **Verification:**
  - Backend pytest suite: **55 passed in 20.61s** (`tests/test_rag_chat.py` + full Modules 1–6 regression).
  - Frontend ESLint & TypeScript build (`npm run lint`, `npm run build`): **0 errors, 0 warnings**, built in 9.46s.
  - Live ChromaDB + Groq LLM (`openai/gpt-oss-120b`) queries & browser E2E verification passed across VPN reset, Dell dock display flickering, and Mars exploration policy (insufficient docs handling) with 0 console/network errors.


---

## Module 8 Checklist: AI-Powered Incident Classification

- [x] **Classification Service & Rules (`services/classifier/`):**
  - Natural language signal extraction via Groq LLM with prompt constraints and JSON output mode.
  - Category mapping for all supported ITSM categories: `Hardware`, `Software`, `Network`, `Access Management`, `Email`, `Security`, `Other`.
  - Assignment group recommendations: `Hardware Support`, `Network Support`, `Software Support`, `Security Support`, `Access Management`, and `Tier 1 Service Desk`.
  - Intelligent local ITSM heuristics fallback (`HEURISTIC_RULES`) to safeguard system availability if Groq is unconfigured or offline.
- [x] **Deterministic ITIL Priority Engine Enforcement:**
  - Strict backend validation: LLM-suggested priority is captured as a recommendation only; final ticket priority is deterministically computed via the ITIL Impact $\times$ Urgency matrix ($P1$ Critical to $P4$ Low).
  - Unvalidated or hallucinated LLM priority suggestions are prevented from controlling ticket priority.
- [x] **Classification Endpoint (`api/routes/classification.py`):**
  - `POST /api/classification/classify` taking natural-language description and returning structured metadata (`title`, `category`, `subcategory`, `impact`, `urgency`, `recommended_priority`, `priority_label`, `assignment_group`, `summary`, `recommended_action`).
- [x] **Interactive Frontend AI Ticket Preview (`components/CreateTicketModal.tsx`, `types/classification.ts`):**
  - Natural language input bar with auto-classify action and sample prompt chips.
  - Live **AI Classification Preview** banner displaying suggested routing group, category, priority, executive summary, and actionable advice.
  - Full employee editing capabilities (review title, confirm category, edit description, reactively adjust impact/urgency) before confirming ticket creation into `/api/tickets`.
- [x] **Verification:**
  - Backend pytest suite: **63 passed in 22.11s** (`tests/test_classification.py` + full Modules 1–7 regression).
  - Frontend ESLint & TypeScript build (`npm run lint`, `npm run build`): **0 errors, 0 warnings**, built in 9.92s.
  - Live API testing verified 5 distinct problem descriptions (Wi-Fi connectivity, Thunderbolt dock flicker, Phishing alert, Okta lockout, and Office VPN outage).
  - Browser end-to-end verification confirmed employee natural-language auto-classification, reactive ITIL matrix editing, and ticket creation into `INC0000011` with 0 console errors.


---

## Module 9 Checklist: Agentic AI Workflow and Human-in-the-Loop Automation

- [x] **Agent Persistence & Audit Models (`models/agent.py`):**
  - `AgentPendingAction`: Staged ticket confirmation payloads (`pending_confirmation`, `confirmed`, `cancelled`) with duplicate-action protection.
  - `AgentToolLog`: Complete execution audit log (`tool_name`, `status`, `summary`, `execution_ms`, sanitized inputs/outputs) per user and conversation.
  - `AgentEscalation`: Technician handoff records capturing escalation summary, relevant conversation transcript, attempted troubleshooting steps, retrieved KB references, and recommended assignment group.
- [x] **8 Independent Backend Tools & Orchestration (`services/agent/tools.py`, `orchestrator.py`):**
  - Implemented `search_knowledge_base`, `classify_incident`, `recommend_priority`, `recommend_assignment_group`, `get_ticket_status`, `prepare_ticket`, `create_ticket_after_confirmation`, and `escalate_to_human`.
  - Backend orchestration validates permissions, parameters, eligibility, and confirmation gates; blocks destructive auto-actions (`close_ticket`, `auto_close_ticket`, `delete_ticket`, `force_create_ticket`) via `AgentSafetyError`.
- [x] **Agentic Workflow Endpoints (`api/routes/agent.py`, `chat.py`):**
  - Integrated orchestration into `POST /api/chat` returning `tool_calls` and optional `pending_action`.
  - Added `GET /api/agent/tools`, `POST /api/agent/prepare-ticket`, `POST /api/agent/confirm`, `POST /api/agent/cancel`, `POST /api/agent/escalate`, `GET /api/agent/escalations`, `POST /api/agent/tickets/{ticket_id}/override` (admin only with `AuditLog`), and `GET /api/agent/logs`.
- [x] **Frontend Human-in-the-Loop UI (`AgentTicketConfirmCard.tsx`, `AISupport.tsx`, `TicketDetails.tsx`):**
  - Executed agent tool badges rendered per AI turn.
  - Editable **Human-in-the-Loop Ticket Preview** card (`Confirm & Create Ticket` / `Cancel`) preventing unconfirmed ticket creation.
  - **AI Escalation & Troubleshooting Handoff** panel and audited **AI Recommendation Override Reason** input on `/tickets/:id`.
- [x] **Verification:**
  - Backend pytest suite: **67 passed in 24.67s** (`tests/test_agent_workflow.py` + full Modules 1–8 regression).
  - Frontend ESLint & TypeScript build (`npm run lint`, `npm run build`): **0 errors, 0 warnings**, built cleanly in 10.28s.
  - Live API smoke workflow (`INC0000012`) & browser E2E verification completed across employee VPN troubleshooting, HITL confirmation, escalation handoff, and admin AI recommendation override.


---

## Module 9A Checklist: Enterprise Notification, Email Communication & Ticket Event System

- [x] **Notification & Email Database Schema (`models/notification.py`, `user.py`, `database/init_db.py`):**
  - Added `Notification` and `EmailDeliveryLog` tables with foreign keys, indexes, UTC timestamps, and unique `event_key` idempotency constraints.
  - Added idempotent `migrate_users_table()` extending `users` with `email_verified` and `email_verified_at`.
- [x] **Event-Driven Notification & SMTP Services (`services/notifications/`):**
  - Implemented `notification_service.py` covering Events A–D (Ticket Submitted, Ticket Assigned, Meaningful Status Changed, Ticket Resolved without auto-closing).
  - Implemented `email_service.py` and HTML-escaped `notification_templates.py` with non-blocking post-commit execution, retry handling, sanitized error logging, dynamic employee DB email lookup, and fixed `ADMIN_NOTIFICATION_EMAIL=bb7578167@gmail.com` alerts.
  - Updated `.env.example`, `backend/.env.example`, and `core/config.py` with `SMTP_*` and `ADMIN_NOTIFICATION_EMAIL` placeholders.
- [x] **API Endpoints (`api/routes/notifications.py`, `auth.py`, `dashboard.py`):**
  - Implemented `GET /api/notifications`, `GET /api/notifications/unread-count`, `PATCH /api/notifications/{id}/read`, `PATCH /api/notifications/read-all`, `GET /api/notifications/email-history`, `GET /api/notifications/config` (admin only), and `POST /api/auth/verify-email`.
  - Extended `GET /api/dashboard/stats` with `recent_notifications`, `recently_assigned_incidents`, and `recently_resolved_incidents`.
- [x] **Employee & Admin Frontend (`NotificationBell.tsx`, `Notifications.tsx`, `TicketList.tsx`, `TicketDetails.tsx`, `AdminDashboard.tsx`, `Profile.tsx`):**
  - Real-time header bell with unread badge, dropdown, "Mark all read", and direct ticket navigation.
  - Full `/notifications` Notification Centre with Unread filter, Email Delivery Logs tab, email verification action, and admin SMTP routing banner.
- [x] **Verification:**
  - Backend pytest suite: **73 passed in 31.71s** (`tests/test_notifications.py` + full Modules 1–9 regression).
  - Frontend ESLint & TypeScript build (`npm run lint`, `npm run build`): **0 errors, 0 warnings**, built cleanly in 12.79s.
  - Full documentation added in `NOTIFICATION_SYSTEM.md`.


---

## Module 10 Checklist: SLA Management and Service Analytics

- [x] **Configurable SLA Policies & Models (`models/sla_policy.py`, `models/ticket.py`, `database/init_db.py`):**
  - Updated `SLAPolicy` with `response_time_minutes`, `response_time_hours`, `resolution_time_hours`, `business_hours_only`, and `escalation_contact`.
  - Updated `Ticket` with `response_deadline` and `first_responded_at`.
  - Added idempotent migrations in `init_db.py` for SQLite database evolution.
  - Configured demo SLA baseline policies:
    - **P1 Critical**: Response 15m (0.25h), Resolution 4h, 24x7 Continuous Calendar time (`business_hours_only=False`).
    - **P2 High**: Response 30m (0.5h), Resolution 8h, 24x7 Continuous Calendar time (`business_hours_only=False`).
    - **P3 Medium**: Response 4h (240m), Resolution 24h, 9x5 Business Hours (`business_hours_only=True`).
    - **P4 Low**: Response 8h (480m), Resolution 48h, 9x5 Business Hours (`business_hours_only=True`).
- [x] **SLA Calculation Service (`services/sla/calculator.py`):**
  - `calculate_calendar_deadline`: 24x7 continuous timeline addition.
  - `calculate_business_deadline`: 9:00 AM - 5:00 PM Monday-Friday business hours engine, skipping non-business hours and weekends.
  - `calculate_ticket_age`: Exact elapsed age formatted in human-readable strings (`2d 4h`, `3h 20m`, `45m`) and decimal hours.
  - `evaluate_ticket_sla_status`: Evaluates response breach, resolution breach, overdue state, near-breach status (<=20% remaining or <=1 hour), and overall compliance.
- [x] **Ticket Workflow Integration (`services/tickets/service.py`):**
  - Automatically calculates `response_deadline` and `sla_deadline` upon ticket creation and on priority recalculations.
  - Automatically tracks `first_responded_at` on first status change or assignment group allocation.
  - Serializes `response_deadline`, `sla_deadline`, `first_responded_at`, `response_breached`, `resolution_breached`, `is_overdue`, `is_near_breach`, `sla_status`, and `ticket_age_display`.
- [x] **Real-Time Analytics Engine & API Endpoints (`services/analytics/service.py`, `api/routes/analytics.py`, `api/routes/sla.py`):**
  - `GET /api/analytics/summary`: KPI metrics (total, open, in-progress, resolved, breaches, avg resolution time, compliance rate %) across dynamic date filters (`7d`, `30d`, `90d`, `all`, custom).
  - `GET /api/analytics/ticket-trends`: Daily created, resolved, and breached volume trends over time.
  - `GET /api/analytics/category-distribution`: Domain distribution across Hardware, Software, Network, Access Mgmt, Email, Security, Other.
  - `GET /api/analytics/priority-distribution`: Severity distribution across P1 through P4.
  - `GET /api/analytics/status-distribution`: Workflow pipeline volume across open, assigned, in_progress, pending, resolved, closed.
  - `GET /api/analytics/workload`: Team queue allocation and capacity breakdown per assignment group.
  - `GET /api/sla/overview`: Full SLA telemetry, compliance breakdown, overdue incidents, and recent breaches.
  - `GET /api/sla/policies`, `POST /api/sla/policies`, `PUT /api/sla/policies/{id}`, `DELETE /api/sla/policies/{id}`: Admin policy CRUD.
- [x] **Executive Frontend Command Center & Governance (`AdminDashboard.tsx`, `AdminSLAManagement.tsx`, `TicketDetails.tsx`):**
  - Admin Dashboard with interactive date range selector (`7 Days`, `30 Days`, `90 Days`, `All Time`), 6 KPI cards with SLA compliance badges, multi-series AreaChart trends, Priority Donut, Category BarChart, Status BarChart, and Group Workload BarChart.
  - Admin SLA Management Center with live compliance meters, policy cards with clock model badges, educational calendar vs business hours documentation, tabbed Overdue/Breached incidents table, and policy modal.
  - Enhanced Ticket Details with live Ticket Age, Response SLA deadline with status badge, and Resolution SLA deadline with overdue/breach indicators.
- [x] **Verification & Documentation:**
  - Backend pytest suite: **85 passed in 29.10s** (`tests/test_sla_analytics.py` + full Modules 1–9 regression).
  - Frontend ESLint & TypeScript build (`npm run lint`, `npm run build`): **0 errors, 0 warnings**, built cleanly in 9.89s.
  - Full documentation added in `docs/SLA_MANAGEMENT.md`.



---

## Module 11 – 13 Checklist: QA, Enterprise UI Redesign, Gmail SMTP & Deployment Readiness

- [x] **Module 11 & 12A — Enterprise Light UI & Accessibility:**
  - Deep Teal (`#087E8B`) and Off-White (`#F7F8F6`) light-only enterprise design system with midnight navy (`#172B3A`) typography and WCAG AA input/table/badge contrast.
  - Fixed 256px desktop sidebar, balanced KPI grids, and responsive Recharts layouts.
- [x] **Module 12B — Email Verification & Live Gmail SMTP:**
  - Single-use SHA-256 verification tokens, expiry checks, resend cooldown rate limits, and gated ticket creation for unverified accounts.
  - Verified live Gmail SMTP (`smtp.gmail.com:587`) delivery to `balaji.poet2312s@gmail.com`.
- [x] **Module 13 — Production Database, Hardening & Cloud Manifests (`DEPLOYMENT.md`):**
  - Added PostgreSQL connection pooling (`psycopg2-binary`), `postgres://` URL normalization, and SQLite-only dialect guard on startup `ALTER TABLE` backfills in `database/init_db.py`.
  - Added `backend/scripts/migrate_sqlite_to_postgres.py` for zero-data-loss SQLite-to-PostgreSQL migration.
  - Enhanced `GET /api/health` to verify real SQL connectivity and ChromaDB path status without leaking secrets.
  - Added startup production environment checks (`Settings.validate_runtime_settings()`) and gated demo login helpers out of production bundles unless `VITE_ENABLE_DEMO_LOGIN=true`.
  - Added `frontend/vercel.json`, `frontend/public/_redirects`, `render.yaml`, `Procfile`, `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.prod.yml`.
  - Verified **136 passed, 0 failed** on backend `pytest` (including empty-index RAG fast path + low-memory `ONNXMiniLM_L6_V2` fallback for 512 MB containers) and clean production `tsc && vite build`.
  - **Live Cloud Deployment Verified:**
    - Frontend deployed on Vercel: `https://nexdesk-ai.vercel.app` (wired to `VITE_API_URL=https://nexdesk-backend-z98v.onrender.com/api`).
    - Backend deployed on Render + Neon PostgreSQL + Groq LLM + Gmail SMTP: `https://nexdesk-backend-z98v.onrender.com`.
    - Live E2E API & Vercel browser UI verification passed across `/api/health`, RBAC login, Admin Dashboard telemetry, Incidents, Notifications, Ticket lifecycle (`INC0000001`), KB upload + ONNX RAG retrieval, and Groq AI Assistant chat (`200 OK`, zero CORS/502 errors).
