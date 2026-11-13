# NexDesk AI – Comprehensive REST API Documentation

Base URL: `http://localhost:8000/api`  
Interactive OpenAPI UI: `http://localhost:8000/docs`  
ReDoc UI: `http://localhost:8000/redoc`

All endpoints return JSON responses. Protected endpoints require standard HTTP Bearer token authentication:
```http
Authorization: Bearer <access_token>
```

---

## 1. Authentication & User Management (`/api/auth`)

### 1.1 Register New Employee
- **Route:** `POST /api/auth/register`
- **Access:** Public
- **Request Body:**
  ```json
  {
    "name": "Jane Doe",
    "email": "jane.doe@nexdesk.ai",
    "password": "Password123!"
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "id": 5,
    "name": "Jane Doe",
    "email": "jane.doe@nexdesk.ai",
    "role": "employee",
    "created_at": "2026-11-13T10:00:00Z"
  }
  ```

### 1.2 User Login
- **Route:** `POST /api/auth/login`
- **Access:** Public
- **Request Body:**
  ```json
  {
    "email": "admin@nexdesk.ai",
    "password": "AdminPassword123!"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "name": "System Administrator",
      "email": "admin@nexdesk.ai",
      "role": "admin"
    }
  }
  ```

### 1.3 Get Current User Profile
- **Route:** `GET /api/auth/me`
- **Access:** Authenticated User
- **Response (200 OK):** Returns current user entity.

### 1.4 List All Users
- **Route:** `GET /api/auth/users`
- **Access:** Admin Only
- **Response (200 OK):** List of user objects.

---

## 2. Incident & Ticket Management (`/api/tickets`)

### 2.1 Create Ticket
- **Route:** `POST /api/tickets`
- **Access:** Authenticated User
- **Request Body:**
  ```json
  {
    "title": "Corporate VPN authentication timeout 504",
    "description": "GlobalProtect client fails to authenticate on gateway vpn-east.nexdesk.ai after flushing DNS.",
    "category": "network",
    "subcategory": "VPN",
    "impact": "high",
    "urgency": "high"
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "id": 19,
    "ticket_number": "INC0000019",
    "title": "Corporate VPN authentication timeout 504",
    "description": "...",
    "category": "network",
    "subcategory": "VPN",
    "impact": "high",
    "urgency": "high",
    "priority": "critical",
    "priority_label": "P1 Critical",
    "status": "assigned",
    "status_label": "Assigned",
    "assigned_group": "Network Support",
    "created_by": "Demo Employee",
    "created_at": "2026-11-13T10:15:00Z",
    "sla_deadline": "2026-11-13T14:15:00Z",
    "response_deadline": "2026-11-13T10:30:00Z",
    "sla_status": "compliant"
  }
  ```

### 2.2 List Tickets
- **Route:** `GET /api/tickets`
- **Access:** Authenticated User (Employees receive only their own tickets; Admins receive organization-wide tickets)
- **Query Parameters:** `q`, `status`, `priority`, `category`, `group_id`, `page` (default 1), `page_size` (default 20, max 100).

### 2.3 Get Ticket Details
- **Route:** `GET /api/tickets/{id}`
- **Access:** Ticket Owner or Admin

### 2.4 Update Ticket
- **Route:** `PATCH /api/tickets/{id}`
- **Access:** Admin (Full fields: status, group_id, priority inputs, resolution_notes) or Employee (`status="closed"` only on own resolved tickets).
- **Request Body:**
  ```json
  {
    "status": "in_progress",
    "group_id": 2
  }
  ```

### 2.5 Get Ticket History Timeline
- **Route:** `GET /api/tickets/{id}/history`
- **Access:** Ticket Owner or Admin
- **Response (200 OK):** Chronological audit trail of field mutations.

---

## 3. Generative AI & RAG Chat (`/api/chat`)

### 3.1 AI Chat & Orchestrated IT Support
- **Route:** `POST /api/chat`
- **Access:** Authenticated User
- **Request Body:**
  ```json
  {
    "conversation_id": "1",
    "message": "My company VPN is not connecting. It shows authentication failed."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "conversation_id": "1",
    "response": "Based on our Corporate VPN Troubleshooting SOP, an authentication failure typically indicates...",
    "rag_used": true,
    "retrieved_chunks_count": 2,
    "sources": [
      {
        "document_title": "Corporate VPN Troubleshooting",
        "source_filename": "VPN_Troubleshooting_Guide.md",
        "page_number": 1,
        "category": "network",
        "score": 0.842
      }
    ],
    "actions": [
      {
        "action_type": "confirm_ticket",
        "label": "Review & Confirm Ticket (P2)"
      }
    ],
    "tool_calls": [
      {
        "tool_name": "search_knowledge_base",
        "status": "success",
        "summary": "Retrieved 2 relevant chunks from ChromaDB"
      }
    ],
    "pending_action": null
  }
  ```

---

## 4. Knowledge Management & Vector Search (`/api/knowledge`)

### 4.1 Upload IT Document
- **Route:** `POST /api/knowledge/upload`
- **Access:** Admin Only
- **Payload:** `multipart/form-data` with `file` (`.pdf`, `.docx`, `.txt`), optional `title`, `category`.
- **Response (201 Created):** Document record with chunk count and SHA-256 hash.

### 4.2 Semantic Vector Search
- **Route:** `GET /api/knowledge/search`
- **Access:** Authenticated User
- **Query Parameters:** `q` (search query), `top_k` (default 5), `category`, `document_id`.

### 4.3 Delete Document
- **Route:** `DELETE /api/knowledge/documents/{id}`
- **Access:** Admin Only (Deletes SQLite metadata and ChromaDB vectors).

---

## 5. Agentic AI & Human-in-the-Loop (`/api/agent`)

### 5.1 List Agent Tools
- **Route:** `GET /api/agent/tools`
- **Access:** Authenticated User

### 5.2 Stage Ticket Proposal
- **Route:** `POST /api/agent/prepare-ticket`
- **Access:** Authenticated User

### 5.3 Confirm & Create Ticket (HITL)
- **Route:** `POST /api/agent/confirm`
- **Access:** Authenticated User (Owner of the staged action)
- **Request Body:**
  ```json
  {
    "confirmation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "Confirmed VPN issue",
    "escalate_to_human": true
  }
  ```

### 5.4 Escalate to Human Support
- **Route:** `POST /api/agent/escalate`
- **Access:** Authenticated User

### 5.5 Admin Override AI Recommendations
- **Route:** `POST /api/agent/tickets/{ticket_id}/override`
- **Access:** Admin Only

---

## 6. Service Analytics & SLA Management (`/api/analytics` & `/api/sla`)

### 6.1 Analytics Summary KPIs
- **Route:** `GET /api/analytics/summary`
- **Access:** Admin Only
- **Query Parameters:** `range` (`7d`, `30d`, `90d`, `all`, `custom`), `start_date`, `end_date`.

### 6.2 Ticket Trends Over Time
- **Route:** `GET /api/analytics/ticket-trends`
- **Access:** Admin Only

### 6.3 SLA Overview & Policy Status
- **Route:** `GET /api/sla/overview`
- **Access:** Admin Only
- **Response (200 OK):** Overall compliance, response/resolution compliance rates, policy breakdown, overdue tickets, and recent breaches.

### 6.4 SLA Policy CRUD
- `GET /api/sla/policies` (Admin)
- `POST /api/sla/policies` (Admin)
- `PUT /api/sla/policies/{id}` (Admin)
- `DELETE /api/sla/policies/{id}` (Admin)

---

## 7. Notifications & Delivery Logs (`/api/notifications`)

- `GET /api/notifications` (List in-app notifications for authenticated user)
- `GET /api/notifications/unread-count` (Get unread badge counter)
- `PATCH /api/notifications/{id}/read` (Mark notification read)
- `PATCH /api/notifications/read-all` (Mark all read)
- `GET /api/notifications/email-history` (Admin only: audit log of outgoing SMTP emails)
- `GET /api/notifications/config` (Admin only: SMTP server configuration status)
