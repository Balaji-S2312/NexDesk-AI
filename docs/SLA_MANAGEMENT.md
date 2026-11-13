# NexDesk AI – SLA Management and Service Analytics Architecture

## 1. Overview
Module 10 introduces enterprise-grade **Service Level Agreement (SLA) Management** and **Service Analytics** to NexDesk AI.
The system provides deterministic ITIL-compliant SLA deadline calculation, real-time breach detection, calendar-time vs. business-hours accounting, ticket age tracking, and an interactive executive analytics dashboard with dynamic date range filtering.

---

## 2. Configurable SLA Policy Matrix

The baseline deployment seeds four standard priority tiers:

| Priority | Tier | Response Target | Resolution Target | Clock Model | Escalation Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P1** | **Critical Outage** | **15 minutes** (0.25h) | **4 hours** | 24x7 Continuous Calendar | `pagerduty-ops@nexdesk.ai` |
| **P2** | **Major Degradation** | **30 minutes** (0.5h) | **8 hours** | 24x7 Continuous Calendar | `tier2-leads@nexdesk.ai` |
| **P3** | **Standard Request** | **4 hours** (240m) | **24 hours** | 9x5 Business Hours (Mon-Fri 09:00-17:00 UTC) | `servicedesk@nexdesk.ai` |
| **P4** | **Minor Inquiry** | **8 hours** (480m) | **48 hours** | 9x5 Business Hours (Mon-Fri 09:00-17:00 UTC) | `servicedesk@nexdesk.ai` |

---

## 3. Calendar Time vs. Business Hours Calculations

### Calendar-Time Deadlines (24x7)
Used for critical infrastructure and security events (P1 & P2). Elapsed time runs continuously 24 hours a day, 7 days a week, including weekends and holidays.
$$\text{Deadline} = \text{Created}_{\text{UTC}} + \Delta t$$

### Business-Hours Deadlines (9x5)
Used for operational requests (P3 & P4).
- Operating window: **Monday through Friday, 09:00 to 17:00 UTC** (8 business hours = 480 business minutes per day).
- Non-business hours (17:00 to 09:00 next day) and weekends (Saturday and Sunday) are strictly **paused/excluded** from the deadline calculation.
- Tickets submitted after 17:00 or on weekends immediately snap to 09:00 on the subsequent Monday or business morning before consuming target minutes.

---

## 4. SLA Status & Breach Telemetry

Each incident is continuously evaluated against its targets:
- `first_responded_at`: Timestamp recorded when an incident is first assigned to an engineer/team or transitioned from `open` to `assigned`, `in_progress`, `pending`, `resolved`, or `closed`.
- **Response Breached**: Triggered if `first_responded_at > response_deadline`, or if `now > response_deadline` and no response has been initiated.
- **Resolution Breached**: Triggered if `resolved_at > sla_deadline`, or if `now > sla_deadline` and ticket is still open.
- **Overdue Incident**: An active, unresolved incident that has passed its `sla_deadline`.
- **Near Breach Warning**: An active ticket within $\le 20\%$ of remaining time or $\le 1\text{ hour}$ from breaching its resolution deadline.
- **Ticket Age**: Exact elapsed duration tracked from `created_at` to `resolved_at` (or current UTC time), formatted in human-readable notation (e.g. `2d 4h`, `3h 20m`, `45m`).

---

## 5. Service Analytics API Endpoints

All analytics endpoints query real SQLite database records and support dynamic date filtering via `?range=7d|30d|90d|all` or `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`:

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/analytics/summary` | `GET` | Core KPIs: Total tickets, open, in-progress, resolved, SLA breaches, avg resolution time, and compliance rates. |
| `/api/analytics/ticket-trends` | `GET` | Daily volume trend: created, resolved, and breached incidents over time. |
| `/api/analytics/category-distribution` | `GET` | Volume and percentage breakdown across categories (Hardware, Software, Network, Access Mgmt, Email, Security, Other). |
| `/api/analytics/priority-distribution` | `GET` | Volume and percentage breakdown across P1 Critical through P4 Low. |
| `/api/analytics/status-distribution` | `GET` | Volume and percentage breakdown across lifecycle statuses (Open, Assigned, In Progress, Pending, Resolved, Closed). |
| `/api/analytics/workload` | `GET` | Allocation and active queue breakdown across assignment groups. |
| `/api/sla/overview` | `GET` | Comprehensive SLA telemetry: overall compliance %, response/resolution compliance %, policy metrics, overdue incidents, and recent breaches. |
| `/api/sla/policies` | `GET` / `POST` | List all SLA policies or create a new policy (admin only). |
| `/api/sla/policies/{id}` | `PUT` / `DELETE` | Update thresholds or delete an SLA policy (admin only). |

---

## 6. Frontend Command Center Experience

- **Admin Dashboard (`/admin/dashboard`)**:
  - Date Range Toggle buttons: `7 Days`, `30 Days`, `90 Days`, `All Time`.
  - 6 KPI Cards with real-time counters and SLA compliance badges.
  - Multi-series AreaChart showing incident inflow, resolution rate, and breach curve.
  - Interactive Recharts Donut & Bar charts for Priority, Category, Status, and Team Workload.
- **SLA Governance Center (`/admin/sla`)**:
  - Live compliance meters for Overall, Response, and Resolution SLAs.
  - Detailed Policy cards with target minutes/hours, clock models, active/resolved counters, and compliance rates.
  - Tabbed Telemetry table for Overdue Incidents and Breached Incidents with direct links to tickets.
  - Policy configuration modal supporting custom minute targets, resolution hours, and business clock toggles.
- **Ticket Details (`/tickets/:id`)**:
  - Dedicated SLA telemetry showing Ticket Age, Response SLA deadline with status badge, and Resolution SLA deadline with breach/overdue indicators.
