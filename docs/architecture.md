# NexDesk AI – System Architecture & Technical Specification

## 1. System Architecture Overview

NexDesk AI is an enterprise-grade IT Service Management (ITSM) automation platform engineered to streamline incident intake, triage, root-cause correlation, and resolution generation through autonomous AI agents and vector-grounded retrieval.

```mermaid
flowchart TB
    subgraph Client["Presentation Tier (Client App)"]
        SPA["React 18 + TypeScript SPA"]
        TailwindCSS["Tailwind CSS + Lucide Icons"]
        Charts["Recharts Analytics Widgets"]
        AxiosLayer["Axios API Client + Interceptors"]
    end

    subgraph APIGateway["Application & Transport Tier"]
        FastAPIServer["FastAPI ASGI Server (Uvicorn)"]
        CORSMiddleware["CORS Policy Middleware"]
        AuthGuard["JWT / Bearer Authentication Guard"]
        APIRouter["Versioned Routing (/api/health, /api/auth, /api/v1)"]
    end

    subgraph ServiceLayer["Domain & Agentic Services"]
        TicketEngine["Ticket Management Service"]
        SLAEngine["SLA & Escalation Engine"]
        AgentOrchestrator["Agentic Coordinator"]
        RAGRetriever["RAG Retrieval Pipeline"]
    end

    subgraph AIPlatform["AI & Inference Tier"]
        GroqLLM["Groq Llama 3 / 3.3 Engine"]
        SentenceTransformers["Sentence Transformers (all-MiniLM-L6-v2)"]
        ChromaStore[("ChromaDB Vector Store (Runbooks & Past Incidents)")]
    end

    subgraph Persistence["Storage & State Tier"]
        SQLAlchemyORM["SQLAlchemy 2.0 ORM"]
        SQLiteDB[("SQLite Database: nexdesk.db")]
    end

    SPA --> AxiosLayer
    AxiosLayer -->|HTTP / JSON| FastAPIServer
    FastAPIServer --> CORSMiddleware --> AuthGuard --> APIRouter
    APIRouter --> TicketEngine
    APIRouter --> SLAEngine
    APIRouter --> AgentOrchestrator

    AgentOrchestrator --> GroqLLM
    AgentOrchestrator --> RAGRetriever
    RAGRetriever --> SentenceTransformers
    SentenceTransformers --> ChromaStore

    TicketEngine --> SQLAlchemyORM
    SLAEngine --> SQLAlchemyORM
    SQLAlchemyORM --> SQLiteDB
```

---

## 2. Authentication & Authorization Architecture

### 2.1 Security Controls & Token Strategy
1. **Password Hashing:** Passwords are never stored in plaintext and never exposed in responses or logs. All passwords are salted and hashed using **Bcrypt** (`bcrypt.gensalt()` with default cost factor).
2. **Access Tokens:** Authentication issues digitally signed **JSON Web Tokens (JWT)** signed using **HMAC-SHA256 (HS256)** with a 60-minute expiration deadline and cryptographic secret (`JWT_SECRET`). Claims include `sub` (user ID), `role`, `email`, `name`, and standard timestamps (`iat`, `exp`).
3. **Role-Based Access Control (RBAC):**
   - **`employee`:** Default role provisioned for all self-service registrations. Employees can only access their own tickets, messages, and profile.
   - **`admin`:** Privileged organizational role with administrative rights over all tickets, users, assignment groups, and SLA policies.
   - **Privilege Escalation Prevention:** Self-service registration (`POST /api/auth/register`) enforces `role="employee"`. Client requests cannot inject or request elevated roles.
4. **Token Persistence & Scoping:**
   - Client stores token in scoped browser storage (`nexdesk_auth_token`) synchronized in React memory via `AuthContext`.
   - Outgoing Axios requests automatically inject the `Authorization: Bearer <token>` header.
   - On load or session restoration, the client probes `GET /api/auth/me`. If rejected (token expired, revoked, or invalid signature), the token is purged immediately and the user is redirected to `/login`.
   - *Architecture Note on HttpOnly Cookies:* For split-domain/SPA development environments without a shared apex cookie domain or dedicated BFF (Backend-For-Frontend), the Bearer token strategy provides standard stateless authentication. In production deployments with unified domain routing, a migration to `Set-Cookie: access_token=...; HttpOnly; Secure; SameSite=Strict` combined with double-submit CSRF tokens is recommended.

```mermaid
sequenceDiagram
    autonumber
    actor User as Employee / Admin
    participant ReactUI as React Frontend
    participant API as FastAPI Backend
    participant Sec as Security Engine (Bcrypt / JWT)
    participant DB as SQLite DB

    User->>ReactUI: Submit Login Credentials (email, password)
    ReactUI->>API: POST /api/auth/login
    API->>DB: Query User by Email
    DB-->>API: Return User Entity
    API->>Sec: Verify Password Hash (Bcrypt checkpw)
    Sec-->>API: Valid Credentials
    API->>Sec: Generate JWT (Claims: sub, role, email, exp)
    Sec-->>API: Signed Access Token
    API-->>ReactUI: 200 OK (access_token, user metadata)
    ReactUI->>ReactUI: Store Token & Mount AuthContext
    ReactUI-->>User: Navigate to Role-Authorized View
```

---

## 3. Database Schema & Relational Models (Module 2)

NexDesk AI utilizes SQLite with SQLAlchemy 2.0 ORM, enforcing strict foreign key constraints (`PRAGMA foreign_keys=ON`) and UTC timezone datetimes across all 9 relational entities:

```mermaid
erDiagram
    users ||--o{ tickets : "requests (requester_id)"
    users ||--o{ tickets : "assigned (assignee_id)"
    users ||--o{ conversations : "participates_in"
    users ||--o{ messages : "sends"
    users ||--o{ documents : "authors"
    users ||--o{ ticket_histories : "initiates"
    users ||--o{ audit_logs : "triggers"

    assignment_groups ||--o{ tickets : "manages"
    sla_policies ||--o{ tickets : "governs"

    tickets ||--o{ conversations : "owns"
    tickets ||--o{ ticket_histories : "tracks"
    conversations ||--o{ messages : "contains"

    users {
        int id PK
        string name
        string email UK "indexed"
        string password_hash
        string role "employee | admin, indexed"
        datetime created_at "UTC"
        datetime updated_at "UTC"
    }

    tickets {
        int id PK
        string title "indexed"
        text description
        string status "open | in_progress | resolved | closed, indexed"
        string priority "low | medium | high | critical, indexed"
        string category "indexed"
        int requester_id FK "users.id, indexed"
        int assignee_id FK "users.id, nullable, indexed"
        int group_id FK "assignment_groups.id, nullable, indexed"
        int sla_policy_id FK "sla_policies.id, nullable, indexed"
        datetime created_at "UTC, indexed"
        datetime updated_at "UTC"
    }

    assignment_groups {
        int id PK
        string name UK "indexed"
        text description
        datetime created_at "UTC"
    }

    sla_policies {
        int id PK
        string name "indexed"
        string priority "indexed"
        int response_time_hours
        int resolution_time_hours
        datetime created_at "UTC"
    }

    conversations {
        int id PK
        int ticket_id FK "tickets.id, indexed"
        int user_id FK "users.id, nullable, indexed"
        datetime created_at "UTC"
        datetime updated_at "UTC"
    }

    messages {
        int id PK
        int conversation_id FK "conversations.id, indexed"
        string sender_type "user | agent | system"
        int sender_id FK "users.id, nullable, indexed"
        text content
        datetime created_at "UTC, indexed"
    }

    documents {
        int id PK
        string title "indexed"
        text content
        string file_path
        string file_type
        string category "indexed"
        int created_by_id FK "users.id, nullable, indexed"
        datetime created_at "UTC"
        datetime updated_at "UTC"
    }

    ticket_histories {
        int id PK
        int ticket_id FK "tickets.id, indexed"
        int user_id FK "users.id, nullable, indexed"
        string field_changed
        text old_value
        text new_value
        datetime created_at "UTC, indexed"
    }

    audit_logs {
        int id PK
        int user_id FK "users.id, nullable, indexed"
        string action "indexed"
        string resource_type "indexed"
        string resource_id
        text details
        string ip_address
        datetime created_at "UTC, indexed"
    }
```


---

## 4. Ticket Management (Module 4)

### 4.1 Ticket model
`tickets` columns: `id`, `ticket_number` (unique, `INC` + 7-digit id), `title`, `description`, `category`, `subcategory`, `impact`, `urgency`, `priority` (derived), `status`, `group_id` (assigned group), `requester_id` (created by), `created_at`, `updated_at`, `sla_deadline`, `resolution_notes`, `resolved_at`, plus `assignee_id`/`sla_policy_id`.
Existing databases are upgraded in place by `migrate_tickets_table()` (idempotent `ALTER TABLE ADD COLUMN`, backfills ticket numbers, SLA deadlines and legacy categories).

### 4.2 Business rules (`app/services/tickets/rules.py`)
| Impact \ Urgency | High | Medium | Low |
| :--- | :--- | :--- | :--- |
| **High** | P1 Critical | P2 High | P3 Medium |
| **Medium** | P2 High | P3 Medium | P4 Low |
| **Low** | P3 Medium | P4 Low | P4 Low |

* Priority is **derived** from impact × urgency and cannot be set directly (`PATCH` rejects a `priority` field).
* SLA deadline = `created_at` + `SLAPolicy.resolution_time_hours` for the priority (P1 4h, P2 8h, P3 24h, P4 48h by default). Changing impact/urgency recalculates priority and deadline, and both changes are recorded.
* Statuses: `open → assigned → in_progress ⇄ pending → resolved → closed`. Setting a group on an `open` ticket auto-moves it to `assigned`. `resolved`/`closed` require resolution notes; reopening clears `resolved_at`.
* Categories: hardware, software, network, access_management, email, security, other.

### 4.3 API (all require a Bearer token)
| Method & path | Access | Notes |
| :--- | :--- | :--- |
| `POST /api/tickets` | any user | Validates, generates number, computes priority/SLA, writes history + audit log. Returns `201`. |
| `GET /api/tickets` | employee: own only · admin: all | Query: `q` (title/description/number, requester for admins), `status`, `priority`, `category`, `group_id`, `page`, `page_size` (≤100). |
| `GET /api/tickets/{id}` | owner or admin | Foreign tickets return `404` (existence is not leaked). |
| `PATCH /api/tickets/{id}` | admin: any editable field · employee: only `status=closed` on own `resolved` ticket | No-op patches write nothing. |
| `GET /api/tickets/{id}/history` | owner or admin | Chronological field changes with old/new value and actor. |
| `GET /api/assignment-groups` | admin | Feeds the group selector. |

Every create/update writes `ticket_histories` rows (one per changed field) and a single `audit_logs` entry (`CREATE_TICKET` / `UPDATE_TICKET`, with actor and client IP). Writes run in one transaction with rollback on failure.

### 4.4 Frontend
`/my-tickets` (own tickets), `/incidents` (admin, all tickets + group filter), both via the shared `TicketList` (debounced server-side search, status/priority/category filters, pagination); `CreateTicketModal` (live priority preview); `/tickets/:id` `TicketDetails` (details, SLA, admin update form with group + status + resolution notes, employee "close" action, history timeline).


---

## 5. Groq LLM Integration & AI Service Architecture (Module 5)

### 5.1 Overview
Module 5 integrates Groq's high-speed inference engine (`openai/gpt-oss-120b` / `llama-3.3-70b-versatile`) as the central Generative AI backbone of NexDesk AI.
All requests are routed securely through backend proxies, preventing client-side API credential leakage.

### 5.2 Backend Components (`app/services/llm/`)
- **`groq_client.py`**:
  - Initializes the Groq client using environment settings (`GROQ_API_KEY`, `GROQ_MODEL`).
  - Implements connection timeouts (30s), rate-limit handling (429), authentication error recovery (401), and sanitized logging (API key masked: `gsk_1j...e9cf`).
  - Supports structured chat completions and handles unconfigured credential states gracefully with user-friendly notices.
- **`prompt_manager.py`**:
  - Encapsulates the enterprise IT assistant system persona.
  - Assembles conversational history context (sliding window of recent turns) and optional runbook context.
- **`response_handler.py`**:
  - Validates and sanitizes LLM output (cleanses reasoning tokens / think tags).
  - Matches knowledge base reference sources (e.g. `NET-104 OpenVPN Recovery`, `HDW-401 Thunderbolt Dock Display`).
  - Generates contextual action buttons (`create_ticket`, `view_runbook`).
- **`schemas.py`**:
  - Defines strict Pydantic schemas for `ChatRequest`, `ChatResponse`, `SourceReference`, `ActionItem`, and `LLMStructuredOutput`.

### 5.3 API Endpoints
- **`POST /api/chat`**:
  - Protected endpoint requiring Bearer JWT authentication.
  - Takes `{ "conversation_id": null | string, "message": string }`.
  - Persists conversation and message history to the relational database (`conversations`, `messages`).
  - Returns `{ "conversation_id": string, "response": string, "sources": [...], "actions": [...] }`.

### 5.4 Frontend Chat Experience (`AISupport.tsx`)
- Interactive real-time chat interface with message bubbles and user/AI avatars.
- Typing indicators with animated bouncing dots while awaiting Groq LLM inference.
- Suggested prompt pills for quick troubleshooting.
- Source reference cards embedded directly below assistant messages.
- Contextual action buttons triggering pre-filled `CreateTicketModal` for instant escalation.
- Conversation reset ("New Chat") and automatic auto-scrolling to recent messages.


---

## 6. RAG Document Ingestion & Vector Storage (Module 6)

### 6.1 Document Processing Pipeline (`app/services/rag/`)
Every administrator upload flows through a deterministic 10-step ingestion pipeline:
1. Receive multipart file upload (`POST /api/knowledge/upload`, admin-only).
2. Validate extension (`.pdf`, `.docx`, `.txt`), MIME/payload signature, non-empty content, maximum size (`MAX_UPLOAD_SIZE_MB=15`), and SHA-256 duplicate file hash (`409 Conflict`).
3. Extract text per page via **PyMuPDF** (`fitz`) for PDFs, **python-docx** for Word documents, and UTF-8 / form-feed decoding for plain text.
4. Preserve exact 1-indexed `page_number` boundaries across chunks.
5. Normalize whitespace, line endings, and control characters (`normalize_text`).
6. Split extracted pages into overlapping token-aware chunks (`CHUNK_SIZE_TOKENS=500`, `CHUNK_OVERLAP_TOKENS=75`, ~4 chars/token approximation with sentence/word boundary splits).
7. Generate 384-dimensional L2-normalized dense vectors using a thread-safe singleton `EmbeddingService` (`sentence-transformers/all-MiniLM-L6-v2` loaded once and reused across requests).
8. Upsert vectors into persistent **ChromaDB** (`CHROMA_PERSIST_DIRECTORY=./chroma_db`, collection `nexdesk_knowledge`, cosine space) storing `chunk_id`, `document_id`, `text`, `embedding`, `source_filename`, `page_number`, `title`, `category`, and `token_count`.
9. Persist relational metadata in SQLite `documents` table (`filename`, `file_size`, `file_hash`, `status`, `error_message`, `page_count`, `chunk_count`, `file_path`) upgraded in-place by `migrate_documents_table()`, plus `audit_logs` (`UPLOAD_DOCUMENT`, `REPROCESS_DOCUMENT`, `DELETE_DOCUMENT`).
10. Return `DocumentOut` with real processing status (`pending` → `processing` → `completed` / `failed`).

### 6.2 Knowledge Management API (Bearer JWT Required)
| Method & path | Access | Notes |
| :--- | :--- | :--- |
| `POST /api/knowledge/upload` | admin only | Multipart upload (`.pdf`, `.docx`, `.txt`); detects duplicates via SHA-256. Returns `201`. |
| `GET /api/knowledge/documents` | any user | Lists documents with filename/title search (`q`), `category`, and `status` filtering. |
| `GET /api/knowledge/documents/{id}` | any user | Returns document metadata and `content_preview`. |
| `POST /api/knowledge/documents/{id}/reprocess` | admin only | Deletes existing vector chunks and re-runs extract → chunk → embed → upsert pipeline. |
| `DELETE /api/knowledge/documents/{id}` | admin only | Removes ChromaDB chunks, disk file, and SQLite row in one lifecycle operation. |
| `GET /api/knowledge/search` | any user | Semantic vector search (`q`, `top_k`, `category`, `document_id`) returning ranked chunks with `page_number` and cosine similarity `score`. |

### 6.3 Frontend Knowledge Base (`KnowledgeBase.tsx`)
- Real-time document inventory fetched from SQLite (`/api/knowledge/documents`) with filename filtering and category tabs.
- Semantic vector search mode querying `/api/knowledge/search` and displaying cited source filename, page number, relevance percentage badge, and chunk excerpt.
- Document detail modal showing ingestion metadata and extracted text preview.
- Admin-only upload modal, reprocess action, and delete confirmation dialog removing both SQLite metadata and ChromaDB vectors.


---

## 7. Retrieval-Augmented Generation Integration (Module 7)

### 7.1 End-to-End 9-Step RAG Chat Flow (`app/services/rag/retriever.py` + `app/api/routes/chat.py`)
1. Receive authenticated employee/admin question (`POST /api/chat`) and persist message turn in SQLite.
2. Augment short contextual follow-ups with recent user query intent when needed.
3. Generate 384-dim query embedding via singleton `EmbeddingService`.
4. Query persistent ChromaDB vector store (`nexdesk_knowledge`) for top-`RAG_TOP_K` (5) candidates.
5. Apply cosine similarity relevance threshold (`RAG_RELEVANCE_THRESHOLD=0.28`), discarding low-relevance noise.
6. Construct bounded `<retrieved_documents>` context (`RAG_MAX_CONTEXT_CHARS=6000`) preserving filename, page number, document title, category, and similarity score.
7. Pass grounded context + recent conversation history to Groq LLM via `prompt_manager.build_chat_messages`.
8. Clean/validate LLM answer, build verified `sources` strictly from retained ChromaDB chunks (never fabricating sources), and generate category-aware `actions` and `follow_up_questions`.
9. Persist assistant message and return `ChatResponse` (`rag_used`, `retrieved_chunks_count`, `sources`, `actions`, `follow_up_questions`).

### 7.2 Prompt Grounding & Safety Rules (`app/services/llm/prompt_manager.py`)
- Ground answers strictly in retrieved Knowledge Base excerpts with explicit `filename` and `page_number` citations.
- Never fabricate internal policies, links, or references; explicitly notify the employee when no retrieved documentation meets the relevance threshold.
- Treat `<retrieved_documents>` strictly as untrusted reference excerpts so embedded prompt-injection text cannot override system instructions.

### 7.3 AI Support Frontend (`AISupport.tsx` + `CreateTicketModal.tsx`)
- Retrieved Document Indicator pill displaying KB grounding status per assistant response.
- Knowledge Source Cards showing `filename`, `Page N`, match score percentage, category, and chunk excerpt.
- One-click Follow-up Question chips, Suggested Troubleshooting actions, Resolved / Not Resolved feedback tracking, and pre-filled `CreateTicketModal` escalation.


---

## 8. AI-Powered Incident Classification (Module 8)

### 8.1 Architecture & Workflow (`app/services/classifier/`)
Module 8 introduces an automated incident triage and classification pipeline that ingests unstructured natural-language problem reports and extracts validated ITSM parameters:
1. **Natural Language Intake:** Employee describes an issue in plain English (e.g. `"My company laptop suddenly stopped connecting to Wi-Fi"`).
2. **Signal Extraction via Groq LLM:** Prompts Groq (`CLASSIFIER_SYSTEM_PROMPT`) with JSON-mode output to extract incident signals: `title`, `category`, `subcategory`, `impact`, `urgency`, `summary`, and `recommended_action`.
3. **Deterministic Backend Priority Engine (`rules.py`):** **MANDATORY SECURITY RULE**: Raw priority output from the LLM is strictly treated as an unvalidated recommendation (`raw_llm_priority`). The final priority (`P1 Critical`, `P2 High`, `P3 Medium`, `P4 Low`) is deterministically calculated by the backend ITIL priority matrix:
   $$\text{Priority} = \text{PRIORITY\_MATRIX}(\text{Impact}, \text{Urgency})$$
   Any hallucinated or invalid LLM priority is superseded by backend business logic.
4. **Assignment Group Recommendation:** Based on category mapping and ITIL domain ownership:
   - `hardware` $\rightarrow$ Hardware Support
   - `network` $\rightarrow$ Network Support
   - `software` / `email` $\rightarrow$ Software Support
   - `security` $\rightarrow$ Security Support
   - `access_management` $\rightarrow$ Access Management
   - `other` $\rightarrow$ Tier 1 Service Desk
5. **Intelligent Local Heuristic Fallback:** If Groq API is unconfigured, rate-limited, or offline, keyword-based heuristics (`HEURISTIC_RULES`) maintain 100% operational uptime without failing ticket workflows.

### 8.2 API Endpoints
- `POST /api/classification/classify` (Bearer Auth required):
  - Request: `{"description": "Problem in natural language"}`
  - Response: Structured classification payload with normalized values, deterministic priority, assignment group, executive summary, and actionable troubleshooting guidance.

### 8.3 Frontend Interactive AI Ticket Preview (`CreateTicketModal.tsx`)
- AI auto-classify input bar with one-click example chips.
- Interactive **AI Classification Preview** card showing category, subcategory, recommended assignment group, and ITIL matrix validation indicator.
- Live reactive form fields allowing employees to review title, edit description, confirm category, adjust impact/urgency, and submit the ticket into the enterprise incident queue.


---

## 9. Agentic AI Workflow and Human-in-the-Loop Automation (Module 9)

### 9.1 Controlled Tool Architecture (`app/services/agent/`)
Module 9 implements controlled AI tool execution through an orchestration service (`orchestrator.py`) and 8 independent, reusable backend tools (`tools.py`):
1. `search_knowledge_base`: Queries ChromaDB vector embeddings for grounded runbooks.
2. `classify_incident`: Extracts structured category, subcategory, impact, and urgency signals.
3. `recommend_priority`: Computes deterministic ITIL priority (`P1`–`P4`) from impact and urgency.
4. `recommend_assignment_group`: Maps incident category to the target enterprise support team.
5. `get_ticket_status`: Retrieves real-time status, priority, and SLA target for a user's ticket (`INCxxxxxxx`).
6. `prepare_ticket`: Stages a `PendingTicketAction` (`status="pending_confirmation"`) with troubleshooting history and KB references without creating a ticket prematurely.
7. `create_ticket_after_confirmation`: Persists the official `Ticket` only after explicit employee confirmation (`confirmation_id`), preventing duplicate executions (`409 Conflict`).
8. `escalate_to_human`: Creates an `AgentEscalation` handoff record with conversation transcript, attempted troubleshooting steps, retrieved KB citations, and recommended assignment group.

### 9.2 Safety Guardrails & Auditability (`app/models/agent.py`, `app/api/routes/agent.py`)
- **No Unconfirmed Ticket Creation:** `prepare_ticket` never inserts a `Ticket` row; only `POST /api/agent/confirm` (`create_ticket_after_confirmation`) creates the ticket after validating ownership and `pending_confirmation` state.
- **Forbidden Auto-Actions:** Destructive or unconfirmed actions (`close_ticket`, `auto_close_ticket`, `delete_ticket`, `force_create_ticket`) are strictly blocked (`AgentSafetyError`) and logged as `status="blocked"`.
- **Execution Logging & Admin Overrides:** Every tool invocation is recorded in `agent_tool_logs` (`AgentToolLog`), and administrators can override AI classification/routing recommendations via `POST /api/agent/tickets/{ticket_id}/override` with mandatory `AuditLog` (`ADMIN_OVERRIDE_AI_RECOMMENDATION`) and `TicketHistory` tracking.

### 9.3 Frontend Human-in-the-Loop Experience (`AISupport.tsx`, `AgentTicketConfirmCard.tsx`, `TicketDetails.tsx`)
- **Executed Agent Tools Badges:** Displays real-time badges for backend tools invoked during each assistant turn.
- **Interactive Ticket Confirmation Card:** Allows employees to review/edit AI-prepared ticket details, inspect attempted troubleshooting and KB references, and click **Confirm & Create Ticket** or **Cancel**.
- **Technician Escalation Handoff & Override UI:** Displays the **AI Escalation & Troubleshooting Handoff** card on `/tickets/:id` and provides an audited **AI Recommendation Override Reason** field for administrators.

---

## 10. Enterprise Notification & Email Event System (Module 9A)

### 10.1 Event-Driven Notification Engine (`app/services/notifications/`)
Module 9A establishes an asynchronous event dispatcher triggered whenever an incident lifecycle event occurs:
- **Events Tracked:** `ticket_created`, `status_updated`, `priority_escalated`, `assigned`, `sla_breach`, `resolution_submitted`.
- **Recipient Routing Matrix:**
  - Ticket Creation $\rightarrow$ Requester (confirmation) & All Admins / Assigned Team.
  - Status / Priority Update $\rightarrow$ Requester & Assigned Engineer.
  - SLA Breach Warning / Overdue $\rightarrow$ Escalation Contacts & Admins.
- **Dual Delivery Channels:**
  1. **In-App Notification Center:** Real-time bell counter in UI header, badge unread count, mark-as-read, and mark-all-read.
  2. **SMTP Email Notification:** HTML/plaintext email delivery with resilient failover. If SMTP is unconfigured or unavailable, notifications gracefully record to `email_delivery_logs` without failing or rolling back the underlying ticket transaction.

---

## 11. SLA Management & Service Analytics Engine (Module 10)

### 11.1 Dual-Clock SLA Calculation Engine (`app/services/sla/`)
NexDesk AI implements an ITIL-compliant SLA engine operating in UTC:
1. **24x7 Continuous Calendar Clock:** Enforced for mission-critical incidents (**P1 Critical**, 15-min response, 4-hour resolution; **P2 High**, 30-min response, 8-hour resolution).
2. **9x5 Business Hours Clock:** Enforced for operational incidents (**P3 Medium**, 4-hour response, 24-hour resolution; **P4 Low**, 8-hour response, 48-hour resolution). Calculations evaluate the 09:00–17:00 active window Monday through Friday and automatically pause and rollover across evenings and weekends.
3. **Real-Time Incident Telemetry:** Live ticket age countdowns, response SLA status (`compliant`, `near_breach`, `response_breached`), resolution SLA status (`compliant`, `resolution_breached`, `both_breached`), and overdue incident tracking.

### 11.2 Service Analytics & Command Center (`app/services/analytics/`)
- **Real-Time SQLite Metric Aggregations:** Computes organization-wide KPIs: Total Tickets, Open Pipeline, In Progress, Resolved, SLA Breaches, Average Resolution Time, and SLA Compliance Rate.
- **Configurable Time Filtering:** Supports standard windows (`7d`, `30d`, `90d`, `all`) and custom date ranges.
- **Telemetry Visualizations (Recharts):**
  - Incident Creation vs. Resolution Trends (AreaChart).
  - Priority Distribution (Donut PieChart).
  - Category Distribution (BarChart).
  - Status Pipeline Distribution (Horizontal BarChart).
  - Assignment Group Workload Balancer (Stacked BarChart).

---

## 12. Security, Quality Assurance & Production Deployment (Module 11 & 12)

### 12.1 Security Controls & Defense-in-Depth
- **Strict Role-Based Access Control (RBAC):** Administrative endpoints (`/api/analytics/*`, `/api/sla/*`, `/api/knowledge/upload`, `/api/auth/users`) strictly require `require_admin`. Unauthorized employee access is rejected with `HTTP 403 Forbidden`.
- **Multi-Tenant Ticket Ownership:** Employees can only retrieve, view history, or patch their own tickets (`requester_id == current_user.id`).
- **Prompt Injection Defense:** External knowledge documents are sanitized and treated as untrusted data blocks.
- **Secret Sanitization:** JWT keys, SMTP credentials, and Groq API tokens are loaded via environment variables and never logged or exposed in client payloads.

### 12.2 Verification & Test Automation
- Comprehensive automated pytest suite covering 125 test scenarios across all 11 modules (`tests/`).
- End-to-end browser telemetry verifying frontend component rendering, responsive breakpoints, and error states.
- Clean TypeScript build and strict ESLint compliance (`--max-warnings 0`).

