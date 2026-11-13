"""
Module 11 – End-to-End Integration / QA tests.

These tests fill coverage gaps across Modules 1-10: authentication edge cases,
role restrictions, Groq failure handling, conversation persistence, ticket
ownership, classification safety, SLA overdue detection and analytics RBAC.
No real Groq calls are made (the LLM client is mocked).
"""
import io
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database.init_db import (
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_PASSWORD,
    DEMO_EMPLOYEE_EMAIL,
    DEMO_EMPLOYEE_PASSWORD,
)
from app.main import app
from app.models.conversation import Message
from app.models.ticket import Ticket
from app.services.llm.groq_client import (
    GroqAuthenticationError,
    GroqClientError,
    GroqRateLimitError,
)
from tests.conftest import TestingSessionLocal

client = TestClient(app)


# ---------------------------------------------------------------- helpers
def _login(email: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin() -> dict:
    return _login(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def employee() -> dict:
    return _login(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)


def _new_employee() -> dict:
    email = f"qa_{uuid.uuid4().hex[:8]}@nexdesk.ai"
    r = client.post(
        "/api/auth/register",
        json={"name": "QA Employee", "email": email, "password": "StrongPass123!"},
    )
    assert r.status_code == 201, r.text
    db = TestingSessionLocal()
    try:
        from app.models.user import User
        u = db.query(User).filter(User.email == email).first()
        if u:
            u.email_verified = True
            db.commit()
    finally:
        db.close()
    return _login(email, "StrongPass123!")


def _ticket_payload(**over) -> dict:
    p = {
        "title": f"QA monitor flicker {uuid.uuid4().hex[:6]}",
        "description": "External monitor flickers every few minutes at my desk.",
        "category": "hardware",
        "subcategory": "Monitor",
        "impact": "medium",
        "urgency": "medium",
    }
    p.update(over)
    return p


# ======================================================= TEST 1 – AUTH
def test_auth_malformed_expired_and_tampered_tokens():
    # malformed
    r = client.get("/api/tickets", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    # missing header
    assert client.get("/api/tickets").status_code in (401, 403)
    # expired token (valid signature, negative lifetime)
    expired = create_access_token(
        subject="1", role="admin", email=DEMO_ADMIN_EMAIL, name="x",
        expires_delta=timedelta(minutes=-5),
    )
    r = client.get("/api/tickets", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    # tampered signature
    good = create_access_token(subject="1", role="admin", email=DEMO_ADMIN_EMAIL, name="x")
    tampered = good[:-4] + ("AAAA" if not good.endswith("AAAA") else "BBBB")
    r = client.get("/api/tickets", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401
    # token for non-existent user
    ghost = create_access_token(subject="999999", role="admin", email="g@x.io", name="g")
    r = client.get("/api/tickets", headers={"Authorization": f"Bearer {ghost}"})
    assert r.status_code == 401


def test_auth_role_claim_in_token_cannot_escalate_privileges(employee):
    """A forged-role token is rejected; role comes from the DB, not the JWT claim."""
    me = client.get("/api/auth/me", headers=employee).json()
    forged = create_access_token(
        subject=str(me["id"]), role="admin", email=me["email"], name=me["name"]
    )
    r = client.get("/api/auth/users", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403


def test_auth_duplicate_registration_and_wrong_password():
    email = f"dup_{uuid.uuid4().hex[:6]}@nexdesk.ai"
    body = {"name": "Dup", "email": email, "password": "StrongPass123!"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code in (400, 409)
    bad = client.post("/api/auth/login", json={"email": email, "password": "WrongPass999!"})
    assert bad.status_code == 401
    unknown = client.post(
        "/api/auth/login", json={"email": "nobody@nexdesk.ai", "password": "WrongPass999!"}
    )
    assert unknown.status_code == 401
    # no user enumeration: same message for both
    assert bad.json()["detail"] == unknown.json()["detail"]


def test_register_cannot_self_assign_admin_role():
    email = f"role_{uuid.uuid4().hex[:6]}@nexdesk.ai"
    r = client.post(
        "/api/auth/register",
        json={"name": "Sneaky", "email": email, "password": "StrongPass123!", "role": "admin"},
    )
    if r.status_code == 201:
        assert r.json()["role"] == "employee"


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/analytics/summary"),
        ("get", "/api/analytics/ticket-trends"),
        ("get", "/api/analytics/category-distribution"),
        ("get", "/api/analytics/priority-distribution"),
        ("get", "/api/analytics/status-distribution"),
        ("get", "/api/analytics/workload"),
        ("get", "/api/sla/overview"),
        ("get", "/api/sla/policies"),
        ("get", "/api/auth/users"),
        ("get", "/api/assignment-groups"),
        ("get", "/api/notifications/config"),
        ("post", "/api/dashboard/seed-demo-tickets"),
    ],
)
def test_admin_only_endpoints_reject_employee_and_accept_admin(method, path, admin, employee):
    assert getattr(client, method)(path).status_code in (401, 403)
    assert getattr(client, method)(path, headers=employee).status_code == 403
    ok = getattr(client, method)(path, headers=admin)
    assert ok.status_code in (200, 201), f"{path}: {ok.status_code} {ok.text[:200]}"


# =================================================== TEST 2 – KNOWLEDGE
def test_knowledge_employee_cannot_upload_or_delete(employee, admin):
    files = {"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")}
    assert client.post("/api/knowledge/upload", headers=employee, files=files).status_code == 403
    assert client.delete("/api/knowledge/documents/1", headers=employee).status_code == 403
    assert client.post("/api/knowledge/documents/1/reprocess", headers=employee).status_code == 403


def test_knowledge_rejects_bad_type_empty_and_missing_doc(admin):
    exe = {"file": ("evil.exe", io.BytesIO(b"MZ\x00\x00"), "application/octet-stream")}
    assert client.post("/api/knowledge/upload", headers=admin, files=exe).status_code in (400, 415, 422)
    empty = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    assert client.post("/api/knowledge/upload", headers=admin, files=empty).status_code in (400, 422)
    assert client.get("/api/knowledge/documents/987654", headers=admin).status_code == 404
    assert client.delete("/api/knowledge/documents/987654", headers=admin).status_code == 404


# ===================================================== TEST 3 – GENAI
@patch("app.api.routes.chat.groq_client.chat_completion", new_callable=AsyncMock)
def test_chat_persistence_and_history_passed_to_llm(mock_chat, employee):
    mock_chat.return_value = "Please restart your laptop and tell me if the issue persists."
    t1 = client.post("/api/chat", headers=employee, json={"message": "My laptop fan is very loud"})
    assert t1.status_code == 200, t1.text
    conv_id = t1.json()["conversation_id"]

    mock_chat.return_value = "Thanks, noted."
    t2 = client.post(
        "/api/chat", headers=employee,
        json={"conversation_id": conv_id, "message": "It is still loud after restart"},
    )
    assert t2.status_code == 200
    assert t2.json()["conversation_id"] == conv_id

    # the second LLM call must include the first turn as context
    sent = mock_chat.call_args_list[-1].args[0]
    joined = " ".join(m["content"] for m in sent)
    assert "My laptop fan is very loud" in joined
    assert "restart your laptop" in joined

    db = TestingSessionLocal()
    try:
        rows = db.query(Message).filter(Message.conversation_id == int(conv_id)).all()
        assert len(rows) == 4
        assert {r.sender_type for r in rows} == {"user", "agent"}
    finally:
        db.close()


@patch("app.api.routes.chat.groq_client.chat_completion", new_callable=AsyncMock)
def test_chat_conversation_isolated_between_users(mock_chat, employee):
    mock_chat.return_value = "ok"
    conv = client.post("/api/chat", headers=employee, json={"message": "Private question A"}).json()[
        "conversation_id"
    ]
    other = _new_employee()
    r = client.post(
        "/api/chat", headers=other,
        json={"conversation_id": conv, "message": "Trying to join someone else's chat"},
    )
    assert r.status_code == 200
    assert r.json()["conversation_id"] != conv
    sent = " ".join(m["content"] for m in mock_chat.call_args.args[0])
    assert "Private question A" not in sent


@pytest.mark.parametrize(
    "exc,needle",
    [
        (GroqAuthenticationError("bad key"), "unconfigured or expired"),
        (GroqRateLimitError("429"), "high volume"),
        (GroqClientError("upstream 500"), "error occurred"),
    ],
)
def test_chat_groq_failures_degrade_gracefully(exc, needle, employee):
    with patch(
        "app.api.routes.chat.groq_client.chat_completion",
        new_callable=AsyncMock,
        side_effect=exc,
    ):
        r = client.post("/api/chat", headers=employee, json={"message": "Outlook will not open"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert needle in body["response"]
    # no secret material in the user-facing text
    assert "gsk_" not in body["response"]
    # the failure notice is persisted as the assistant turn
    db = TestingSessionLocal()
    try:
        last = (
            db.query(Message)
            .filter(Message.conversation_id == int(body["conversation_id"]))
            .order_by(Message.id.desc())
            .first()
        )
        assert last.sender_type == "agent"
    finally:
        db.close()


@patch("app.api.routes.chat.groq_client.chat_completion", new_callable=AsyncMock)
def test_chat_missing_knowledge_reports_no_sources(mock_chat, employee):
    mock_chat.return_value = "I could not find documentation for that."
    r = client.post(
        "/api/chat", headers=employee,
        json={"message": "How do I configure the quantum flux capacitor firmware?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rag_used"] is False
    assert body["sources"] == []


def test_chat_rejects_whitespace_only_message(employee):
    assert client.post("/api/chat", headers=employee, json={"message": "     "}).status_code == 422


# ============================================ TEST 4 – INCIDENT MGMT
def test_ticket_ownership_get_history_and_patch(admin, employee):
    mine = client.post("/api/tickets", headers=employee, json=_ticket_payload())
    assert mine.status_code == 201, mine.text
    tid = mine.json()["id"]
    other = _new_employee()

    for path in (f"/api/tickets/{tid}", f"/api/tickets/{tid}/history"):
        assert client.get(path, headers=other).status_code in (403, 404), path
        assert client.get(path, headers=employee).status_code == 200, path
    assert (
        client.patch(f"/api/tickets/{tid}", headers=other, json={"status": "closed"}).status_code
        in (403, 404)
    )
    # other employee's list does not include my ticket
    ids = [t["id"] for t in client.get("/api/tickets", headers=other).json()["items"]]
    assert tid not in ids
    # unknown ticket
    assert client.get("/api/tickets/9999999", headers=admin).status_code == 404


def test_ticket_status_lifecycle_and_history_timeline(admin, employee):
    t = client.post("/api/tickets", headers=employee, json=_ticket_payload()).json()
    tid = t["id"]
    assert t["status"] in ("open", "assigned")
    assert t["priority"] == "medium"

    grp = client.get("/api/assignment-groups", headers=admin).json()[0]
    r = client.patch(
        f"/api/tickets/{tid}", headers=admin, json={"group_id": grp["id"], "status": "in_progress"}
    )
    assert r.status_code == 200, r.text
    r = client.patch(
        f"/api/tickets/{tid}", headers=admin,
        json={"status": "resolved", "resolution_notes": "Replaced DisplayPort cable."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"

    hist = client.get(f"/api/tickets/{tid}/history", headers=admin).json()
    fields = [h["field_changed"] for h in hist]
    assert "status" in fields
    stamps = [h["created_at"] for h in hist]
    assert stamps == sorted(stamps, reverse=True) or stamps == sorted(stamps)
    # employee can read own history
    assert client.get(f"/api/tickets/{tid}/history", headers=employee).status_code == 200


def test_ticket_priority_comes_from_matrix_not_client(employee):
    r = client.post(
        "/api/tickets", headers=employee,
        json=_ticket_payload(impact="low", urgency="low", priority="critical"),
    )
    assert r.status_code in (201, 422)
    if r.status_code == 201:
        assert r.json()["priority"] == "low"


@patch("app.services.classifier.service.groq_client.chat_completion", new_callable=AsyncMock)
def test_classification_llm_cannot_override_backend_priority(mock_llm, employee):
    # LLM tries to force P1 for a low-impact / low-urgency cosmetic problem
    mock_llm.return_value = (
        '{"title":"Wallpaper issue","category":"Software","subcategory":"OS",'
        '"impact":"Low","urgency":"Low","recommended_priority":"P1",'
        '"assignment_group":"Software Support","summary":"x","recommended_action":"y"}'
    )
    r = client.post(
        "/api/classification/classify", headers=employee,
        json={"description": "My desktop wallpaper looks slightly blurry on one monitor."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["recommended_priority"] == "P4"


@patch("app.services.classifier.service.groq_client.chat_completion", new_callable=AsyncMock)
@pytest.mark.parametrize("llm_output", ["this is not json at all", '{"category": 42}', ""])
def test_classification_survives_bad_llm_output(mock_llm, llm_output, employee):
    mock_llm.return_value = llm_output
    r = client.post(
        "/api/classification/classify", headers=employee,
        json={"description": "My company laptop suddenly stopped connecting to Wi-Fi."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] == "Network"
    assert body["assignment_group"] == "Network Support"
    assert body["recommended_priority"] in {"P1", "P2", "P3", "P4"}


@patch("app.services.classifier.service.groq_client.chat_completion", new_callable=AsyncMock)
def test_classification_survives_groq_outage(mock_llm, employee):
    mock_llm.side_effect = GroqClientError("down")
    r = client.post(
        "/api/classification/classify", headers=employee,
        json={"description": "VPN gateway timeout 504 whenever I connect from home."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["category"] == "Network"


# =========================================== TEST 5 – AGENT WORKFLOW
def test_agent_prepare_confirm_duplicate_and_cross_user(employee):
    prep = client.post(
        "/api/agent/prepare-ticket", headers=employee,
        json={"description": "Teams keeps crashing at startup on my laptop.",
              "attempted_troubleshooting": ["Reinstalled Teams"]},
    )
    assert prep.status_code == 200, prep.text
    cid = prep.json()["confirmation_id"]

    db = TestingSessionLocal()
    before = db.query(Ticket).count()
    db.close()

    other = _new_employee()
    assert client.post("/api/agent/confirm", headers=other, json={"confirmation_id": cid}).status_code == 403
    assert client.post("/api/agent/confirm", headers=employee, json={"confirmation_id": "nope"}).status_code in (404, 422)

    ok = client.post("/api/agent/confirm", headers=employee, json={"confirmation_id": cid})
    assert ok.status_code == 201, ok.text
    assert client.post("/api/agent/confirm", headers=employee, json={"confirmation_id": cid}).status_code == 409

    db = TestingSessionLocal()
    assert db.query(Ticket).count() == before + 1  # exactly one ticket despite two confirms
    db.close()


def test_agent_endpoints_require_authentication():
    for method, path in [
        ("get", "/api/agent/tools"),
        ("post", "/api/agent/prepare-ticket"),
        ("post", "/api/agent/confirm"),
        ("post", "/api/agent/escalate"),
        ("get", "/api/agent/logs"),
    ]:
        assert getattr(client, method)(path).status_code in (401, 403), path


# ================================================ TEST 6 – SLA / ANALYTICS
def test_overdue_ticket_surfaces_in_sla_overview_and_kpis(admin, employee):
    t = client.post("/api/tickets", headers=employee, json=_ticket_payload()).json()
    db = TestingSessionLocal()
    try:
        row = db.query(Ticket).filter(Ticket.id == t["id"]).first()
        past = datetime.now(timezone.utc) - timedelta(hours=100)
        row.created_at = past - timedelta(hours=1)
        row.response_deadline = past
        row.sla_deadline = past
        row.resolution_deadline = past if hasattr(row, "resolution_deadline") else None
        db.commit()
    finally:
        db.close()

    ov = client.get("/api/sla/overview", headers=admin).json()
    nums = {i["ticket_number"] for i in ov["overdue_incidents"]} | {
        i["ticket_number"] for i in ov["recent_breaches"]
    }
    assert t["ticket_number"] in nums
    assert ov["total_breached"] >= 1
    assert 0 <= ov["overall_compliance_rate"] <= 100

    detail = client.get(f"/api/tickets/{t['id']}", headers=admin).json()
    assert detail["is_overdue"] is True
    assert detail["sla_status"] in ("breached", "both_breached", "resolution_breached", "overdue")


def test_analytics_totals_are_consistent_and_date_filters_nest(admin):
    s7 = client.get("/api/analytics/summary?range=7d", headers=admin).json()
    s90 = client.get("/api/analytics/summary?range=90d", headers=admin).json()
    sall = client.get("/api/analytics/summary?range=all", headers=admin).json()
    assert s7["total_tickets"] <= s90["total_tickets"] <= sall["total_tickets"]
    assert sall["open_tickets"] + sall["in_progress_tickets"] + sall["resolved_tickets"] <= sall["total_tickets"]

    for path in ("category-distribution", "priority-distribution", "status-distribution"):
        items = client.get(f"/api/analytics/{path}?range=all", headers=admin).json()
        assert sum(i["count"] for i in items) == sall["total_tickets"], path

    custom = client.get(
        "/api/analytics/summary?range=custom&start_date=2000-01-01&end_date=2000-01-02", headers=admin
    )
    assert custom.status_code == 200
    assert custom.json()["total_tickets"] == 0


def test_analytics_invalid_range_does_not_500(admin):
    r = client.get("/api/analytics/summary?range=banana", headers=admin)
    assert r.status_code in (200, 400, 422)
    r = client.get("/api/analytics/summary?range=custom&start_date=garbage", headers=admin)
    assert r.status_code in (200, 400, 422)


# ================================================ misc platform checks
def test_health_and_unknown_route():
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/definitely-not-a-route").status_code == 404


def test_ticket_validation_errors_are_422(employee):
    for bad in (
        _ticket_payload(title=""),
        _ticket_payload(description=""),
        _ticket_payload(category="not-a-category"),
        _ticket_payload(impact="extreme"),
    ):
        assert client.post("/api/tickets", headers=employee, json=bad).status_code == 422
