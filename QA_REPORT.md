# NexDesk AI – QA Report (Module 11)

Date: 2026-11-13. Only results actually observed in this session are listed.

## 1. Summary

| Suite | Result |
|---|---|
| Backend pytest (`python -m pytest tests -q`) | **125 passed, 0 failed** (85 pre-existing + 40 new in `tests/test_integration_qa.py`) |
| Live HTTP API integration (`running server :8000`, scratch script, 46 checks) | **46 passed, 0 failed** |
| Frontend TypeScript (`npx tsc -b`) | exit 0, no errors |
| ESLint (`npm run lint`, `--max-warnings 0`) | exit 0, 0 errors / 0 warnings |
| Frontend production build (`npm run build`) | exit 0 (built in ~9s; chunk-size warning, see limitations) |
| Browser E2E (Module 11 subagent, steps A–G) | 7/7 steps PASS as reported by the subagent |

Before-fix baseline (start of Module 11): 85 passed, tsc/lint/build all exit 0.

## 2. Defect found and fixed

### BUG-1 (Security / Authorization) – FIXED
**Analytics and SLA endpoints were readable by any authenticated employee.**
`/api/analytics/*`, `/api/sla/overview` and `/api/sla/policies` used `get_current_user`, so an employee could read organisation-wide metrics and the SLA overdue/breach lists, which include other users' ticket numbers, titles and requester names. The frontend hid the pages, but the API did not enforce it.

Fix: `backend/app/api/routes/analytics.py` and `backend/app/api/routes/sla.py` now use `require_admin` on every endpoint. Only admin pages call these endpoints (checked in `frontend/src`), so no UI change was needed.
Regression tests: `test_admin_only_endpoints_reject_employee_and_accept_admin` (12 parametrised endpoints) and the live-API checks (`employee 403 /analytics/summary`, `/sla/overview`, `/sla/policies`).

No other failures were found in the backend suites, so no other code was changed. The two failures during test authoring were wrong assumptions in my new tests, not product bugs (history field is `field_changed`; SLA status value is `both_breached`). Both tests were corrected.

## 3. Tests executed by area

### Test 1 – Authentication (PASS)
Employee and admin login; invalid credentials (401, identical message for unknown user and wrong password, so no user enumeration); malformed, expired, tampered-signature and unknown-user tokens (401); missing token; forged `role=admin` JWT claim does not elevate an employee (role is read from the DB); duplicate registration rejected; self-assigned admin role at registration not honoured; 12 admin-only endpoints reject employee and accept admin.

### Test 2 – Knowledge management (PASS)
Existing `test_knowledge.py` covers PDF, DOCX and TXT upload, text extraction, token-aware chunking and overlap, embedding singleton and 384 dimensions, ChromaDB storage, search, reprocess and deletion. New tests cover employee upload, delete and reprocess (403), rejected `.exe` and empty files, and 404 for a missing document. Live run: admin TXT upload gave 201 with chunks; employee upload 403; semantic search found the document; delete returned 200, then 404; the deleted document no longer appears in search results.
Note: live-server upload used TXT only. PDF and DOCX are covered by the pytest end-to-end test.

### Test 3 – Generative AI (PASS)
Groq is mocked in pytest. The live run called the real Groq API.
- Chat persistence: 4 messages stored for 2 turns, and the earlier turn is sent to the LLM as context.
- Conversation isolation: another user's `conversation_id` creates a new conversation and does not leak history.
- API failure handling: auth, rate-limit and generic Groq errors return 200 with a user-facing notice, no key material in the text, and the notice is persisted.
- Missing knowledge: `rag_used=false`, no sources.
- Whitespace-only message returns 422.
- Live: real Groq reply with `rag_used=true` and 1 source; the follow-up turn stays in the same conversation.

### Test 4 – Incident management (PASS)
Priority matrix (9 combinations); ticket creation and validation (422 for empty title, empty description, bad category, bad impact); client-supplied priority ignored; assignment recommendation (Wi-Fi gives Network Support); lifecycle open → in_progress → resolved with history; resolution notes required; history timeline readable by owner and admin; ownership restrictions (other employee gets 403/404 on GET, history and PATCH, and the ticket is absent from their list); employee cannot set admin-only status; classification: an LLM-forced P1 for a trivial issue is overridden to P4, garbage, empty or malformed LLM output falls back to heuristics, and a Groq outage still classifies.

### Test 5 – Agent workflow (PASS)
Existing HITL test covers the full chain (KB search, prepare, confirm, ticket, escalation, override, audit). New tests: cross-user confirm (403), unknown confirmation id, exactly one ticket created despite two confirms (second returns 409), and agent endpoints require authentication. Live: prepare 200, confirm 201, duplicate 409, escalate 201.

### Test 6 – SLA and analytics (PASS)
Existing tests cover calendar and business-hours calculation, weekend rollover, ticket age and SLA status. New tests: a ticket whose deadlines are moved to the past appears in the SLA overview and in `is_overdue`/`both_breached`; the 7d ≤ 90d ≤ all totals nest; category, priority and status distribution counts each sum to the total; a custom date range with no data returns 0; invalid range and date values do not return 500. Live: all 5 analytics endpoints, and summary for 7d, 30d, 90d and all.

### Test 7 – Frontend (PASS, subagent-reported)
Run by a browser subagent against `http://127.0.0.1:5173`. The host confirmed that only that origin was visited. Findings are the subagent's own observations; I did not repeat each step by hand. A final screenshot is at `browser_evidence/e599ca9d-7def-465b-bc50-433016498328/final_step_59.png`.
- Login validation, wrong-password banner and employee login all behaved correctly.
- All employee routes load. Direct navigation to the 5 admin URLs redirects away with no admin data shown.
- The Create Ticket modal validates; ticket INC0000019 was created, its history timeline renders, and search and the priority and category filters work.
- AI chat shows a loading state, then a grounded answer with source cards, action buttons and follow-up chips.
- Admin: all routes render; KPI cards, 5 charts and the 4 date filters work; status update to In Progress shows a toast and a history entry.
- Responsive at 390×844 and 768×1024: hamburger drawer present, no horizontal overflow.
- Console: no errors or uncaught exceptions. The only 4xx was the intentional 401 from the wrong-password test.

## 4. Counts

| | Count |
|---|---|
| pytest tests executed | 125 |
| pytest passed / failed | 125 / 0 |
| Live API checks executed | 46 (passed 46, failed 0) |
| Browser steps | 7 (passed 7) |
| Defects found in product code | 1 (fixed) |
| Remaining open bugs | 0 confirmed (see limitations) |

## 5. Known limitations and remaining issues (not fixed)

1. **Bundle size**: production JS is ~872 kB (237 kB gzip), which triggers Vite's >500 kB warning. No route-level code splitting. Not a functional bug.
2. **Deprecation warning**: `app/api/routes/agent.py` uses `HTTP_422_UNPROCESSABLE_ENTITY` (deprecated in Starlette, which suggests `HTTP_422_UNPROCESSABLE_CONTENT`). Harmless today.
3. **Groq timeout/retry**: failure handling was tested with mocked exceptions and a live happy path. A real network timeout or real rate-limit response was not triggered.
4. **SMTP**: email delivery paths are tested with mocks and an unconfigured SMTP (existing Module 9A tests). No real mail server was used.
5. **Business-time SLA** uses a fixed 09:00–17:00 Mon–Fri window in UTC with no holiday calendar and no per-user time zones (documented in `docs/SLA_MANAGEMENT.md`).
6. **Authorization scope**: all authenticated users can list and read knowledge documents and search results (intended, since the RAG assistant uses them). Only admins can upload, delete or reprocess.
7. **Browser coverage**: UI checks were done in one browser, and visually only. There are no automated frontend unit or e2e tests (no Vitest/Playwright suite) in the repo.
8. **Test data in the live DB**: the live API check and browser run added demo tickets and notifications to `backend/nexdesk.db` (the uploaded QA document was deleted). The pytest suite uses an isolated in-memory DB.
9. **Server restart required**: BUG-1 takes effect only after the backend restarts. The running server was restarted and the live checks ran against the fixed build.

## 6. Files changed in Module 11

- `backend/app/api/routes/analytics.py` – admin-only
- `backend/app/api/routes/sla.py` – admin-only
- `backend/tests/test_integration_qa.py` – 40 new tests
- `QA_REPORT.md` – this report
