import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.init_db import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD
from app.models.audit_log import AuditLog
from app.services.tickets.rules import PRIORITY_MATRIX, calculate_priority
from tests.conftest import TestingSessionLocal

client = TestClient(app)


# ---------- helpers ----------
def _login(email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin():
    return _login(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)


def _new_employee():
    email = f"emp_{uuid.uuid4().hex[:8]}@nexdesk.ai"
    pw = "StrongPass123!"
    r = client.post("/api/auth/register", json={"name": "Test Employee", "email": email, "password": pw})
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
    return _login(email, pw)


def _payload(**over):
    p = {
        "title": f"Printer jam {uuid.uuid4().hex[:6]}",
        "description": "The third floor printer jams on every duplex job.",
        "category": "hardware",
        "subcategory": "Printer",
        "impact": "medium",
        "urgency": "medium",
    }
    p.update(over)
    return p


def _create(headers, **over):
    r = client.post("/api/tickets", json=_payload(**over), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _group_id(admin):
    r = client.get("/api/assignment-groups", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()[0]["id"], r.json()[0]["name"]


# ---------- priority matrix ----------
@pytest.mark.parametrize("impact,urgency,expected", [
    ("high", "high", "critical"), ("high", "medium", "high"), ("high", "low", "medium"),
    ("medium", "high", "high"), ("medium", "medium", "medium"), ("medium", "low", "low"),
    ("low", "high", "medium"), ("low", "medium", "low"), ("low", "low", "low"),
])
def test_priority_matrix(impact, urgency, expected):
    assert calculate_priority(impact, urgency) == expected
    assert len(PRIORITY_MATRIX) == 9


# ---------- create ----------
def test_create_ticket_workflow(admin):
    emp = _new_employee()
    t = _create(emp, impact="high", urgency="high")
    assert t["ticket_number"] == f"INC{t['id']:07d}"
    assert t["priority"] == "critical" and t["priority_label"] == "P1 Critical"
    assert t["status"] == "open"
    assert t["assigned_group"] is None
    assert t["created_by"] == "Test Employee"
    assert t["sla_deadline"] is not None and t["sla_breached"] is False
    assert t["created_at"] and t["updated_at"]

    # SLA deadline = created + 4h for P1 (seeded policy)
    from datetime import datetime
    created = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
    deadline = datetime.fromisoformat(t["sla_deadline"].replace("Z", "+00:00"))
    assert round((deadline - created).total_seconds() / 3600) == 4

    # history: creation entry, audit log entry
    h = client.get(f"/api/tickets/{t['id']}/history", headers=emp).json()
    assert len(h) == 1 and h[0]["field_changed"] == "created"
    db = TestingSessionLocal()
    try:
        logs = db.query(AuditLog).filter(AuditLog.action == "CREATE_TICKET", AuditLog.resource_id == str(t["id"])).all()
        assert len(logs) == 1
    finally:
        db.close()


def test_ticket_numbers_unique():
    emp = _new_employee()
    nums = {_create(emp)["ticket_number"] for _ in range(3)}
    assert len(nums) == 3


@pytest.mark.parametrize("bad", [
    {"title": "abc"},
    {"description": "short"},
    {"category": "plumbing"},
    {"impact": "extreme"},
    {"urgency": None},
    {"title": "      "},
])
def test_create_validation(bad):
    emp = _new_employee()
    r = client.post("/api/tickets", json=_payload(**bad), headers=emp)
    assert r.status_code == 422


def test_requires_authentication():
    assert client.post("/api/tickets", json=_payload()).status_code in (401, 403)
    assert client.get("/api/tickets").status_code in (401, 403)
    assert client.get("/api/tickets/1").status_code in (401, 403)


# ---------- ownership ----------
def test_employee_only_sees_own_tickets(admin):
    a, b = _new_employee(), _new_employee()
    ta = _create(a)
    tb = _create(b)

    ids_a = {t["id"] for t in client.get("/api/tickets", headers=a).json()["items"]}
    assert ta["id"] in ids_a and tb["id"] not in ids_a

    assert client.get(f"/api/tickets/{tb['id']}", headers=a).status_code == 404
    assert client.get(f"/api/tickets/{tb['id']}/history", headers=a).status_code == 404
    assert client.patch(f"/api/tickets/{tb['id']}", json={"status": "closed"}, headers=a).status_code == 404

    # admin sees both
    all_ids = {t["id"] for t in client.get("/api/tickets?page_size=100", headers=admin).json()["items"]}
    assert {ta["id"], tb["id"]} <= all_ids


def test_employee_cannot_modify_ticket_fields(admin):
    emp = _new_employee()
    t = _create(emp)
    for body in ({"status": "resolved"}, {"title": "Changed title here"}, {"group_id": 1}, {"impact": "low"}):
        r = client.patch(f"/api/tickets/{t['id']}", json=body, headers=emp)
        assert r.status_code == 403, (body, r.text)
    # cannot close while not resolved
    assert client.patch(f"/api/tickets/{t['id']}", json={"status": "closed"}, headers=emp).status_code == 403


def test_employee_can_close_own_resolved_ticket(admin):
    emp = _new_employee()
    t = _create(emp)
    r = client.patch(f"/api/tickets/{t['id']}", json={"status": "resolved", "resolution_notes": "Cleared the jam."}, headers=admin)
    assert r.status_code == 200
    r = client.patch(f"/api/tickets/{t['id']}", json={"status": "closed"}, headers=emp)
    assert r.status_code == 200 and r.json()["status"] == "closed"


def test_assignment_groups_admin_only():
    emp = _new_employee()
    assert client.get("/api/assignment-groups", headers=emp).status_code == 403


# ---------- admin updates ----------
def test_admin_update_records_history_and_audit(admin):
    emp = _new_employee()
    t = _create(emp)
    gid, gname = _group_id(admin)

    r = client.patch(f"/api/tickets/{t['id']}", json={"group_id": gid}, headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "assigned"           # auto-moved
    assert body["assigned_group"] == gname
    assert body["updated_at"] >= t["updated_at"]

    r = client.patch(f"/api/tickets/{t['id']}", json={"status": "in_progress"}, headers=admin)
    assert r.json()["status"] == "in_progress"

    hist = client.get(f"/api/tickets/{t['id']}/history", headers=admin).json()
    fields = [(h["field_changed"], h["old_value"], h["new_value"], h["changed_by"]) for h in hist]
    assert ("assigned_group", None, gname, "System Administrator") in fields
    assert ("status", "open", "assigned", "System Administrator") in fields
    assert ("status", "assigned", "in_progress", "System Administrator") in fields

    db = TestingSessionLocal()
    try:
        assert db.query(AuditLog).filter(AuditLog.action == "UPDATE_TICKET", AuditLog.resource_id == str(t["id"])).count() == 2
    finally:
        db.close()


def test_noop_patch_records_nothing(admin):
    emp = _new_employee()
    t = _create(emp)
    r = client.patch(f"/api/tickets/{t['id']}", json={"title": t["title"], "status": "open"}, headers=admin)
    assert r.status_code == 200
    assert len(client.get(f"/api/tickets/{t['id']}/history", headers=admin).json()) == 1
    assert r.json()["updated_at"] == t["updated_at"]


def test_impact_urgency_change_recalculates_priority_and_sla(admin):
    emp = _new_employee()
    t = _create(emp, impact="low", urgency="low")
    assert t["priority"] == "low"
    r = client.patch(f"/api/tickets/{t['id']}", json={"impact": "high", "urgency": "high"}, headers=admin)
    body = r.json()
    assert body["priority"] == "critical" and body["sla_deadline"] != t["sla_deadline"]
    fields = {h["field_changed"] for h in client.get(f"/api/tickets/{t['id']}/history", headers=admin).json()}
    assert {"impact", "urgency", "priority", "sla_deadline"} <= fields


def test_priority_cannot_be_set_directly(admin):
    emp = _new_employee()
    t = _create(emp)
    r = client.patch(f"/api/tickets/{t['id']}", json={"priority": "critical"}, headers=admin)
    assert r.status_code == 422


def test_resolution_requires_notes(admin):
    emp = _new_employee()
    t = _create(emp)
    r = client.patch(f"/api/tickets/{t['id']}", json={"status": "resolved"}, headers=admin)
    assert r.status_code == 422
    r = client.patch(f"/api/tickets/{t['id']}", json={"status": "resolved", "resolution_notes": "Replaced toner."}, headers=admin)
    assert r.status_code == 200
    assert r.json()["resolved_at"] is not None and r.json()["resolution_notes"] == "Replaced toner."
    # reopening clears resolved_at
    r = client.patch(f"/api/tickets/{t['id']}", json={"status": "in_progress"}, headers=admin)
    assert r.json()["resolved_at"] is None


def test_invalid_group_and_status(admin):
    emp = _new_employee()
    t = _create(emp)
    assert client.patch(f"/api/tickets/{t['id']}", json={"group_id": 999999}, headers=admin).status_code == 422
    assert client.patch(f"/api/tickets/{t['id']}", json={"status": "bogus"}, headers=admin).status_code == 422
    assert client.patch("/api/tickets/99999999", json={"status": "pending"}, headers=admin).status_code == 404


# ---------- search / filter / pagination ----------
def test_search_and_filters(admin):
    emp = _new_employee()
    token = uuid.uuid4().hex[:10]
    t1 = _create(emp, title=f"Zebra {token} VPN down", category="network", impact="high", urgency="high")
    t2 = _create(emp, title=f"Zebra {token} mailbox full", category="email", impact="low", urgency="low")

    def ids(qs, headers=emp):
        r = client.get(f"/api/tickets?{qs}", headers=headers)
        assert r.status_code == 200, r.text
        return {t["id"] for t in r.json()["items"]}

    assert ids(f"q={token}") == {t1["id"], t2["id"]}
    assert ids(f"q={token}&category=network") == {t1["id"]}
    assert ids(f"q={token}&priority=low") == {t2["id"]}
    assert ids(f"q={token}&priority=critical") == {t1["id"]}
    assert ids(f"q={t1['ticket_number']}") == {t1["id"]}
    assert ids(f"q={token}&status=resolved") == set()
    assert ids(f"q={token}&status=open") == {t1["id"], t2["id"]}
    assert ids(f"q={token}", admin) == {t1["id"], t2["id"]}
    assert ids("q=Test+Employee", admin) >= {t1["id"], t2["id"]}   # admin can search by requester
    assert client.get("/api/tickets?priority=urgent", headers=emp).status_code == 422

    gid, _ = _group_id(admin)
    client.patch(f"/api/tickets/{t1['id']}", json={"group_id": gid}, headers=admin)
    assert t1["id"] in ids(f"group_id={gid}&page_size=100", admin)


def test_pagination():
    emp = _new_employee()
    for _ in range(3):
        _create(emp)
    r = client.get("/api/tickets?page_size=2&page=1", headers=emp).json()
    assert r["total"] == 3 and len(r["items"]) == 2
    r2 = client.get("/api/tickets?page_size=2&page=2", headers=emp).json()
    assert len(r2["items"]) == 1
    assert client.get("/api/tickets?page_size=1000", headers=emp).status_code == 422


# ---------- seed + dashboard integration ----------
def test_dashboard_reflects_tickets(admin):
    emp = _new_employee()
    _create(emp)
    s = client.get("/api/dashboard/stats", headers=emp).json()
    assert s["metrics"]["total_tickets"] == 1 and s["metrics"]["open_tickets"] == 1
    a = client.get("/api/dashboard/stats", headers=admin).json()
    assert a["metrics"]["total_incidents"] >= 1
    assert sum(p["count"] for p in a["priority_distribution"]) == a["metrics"]["total_incidents"]


def test_seed_demo_is_admin_only():
    emp = _new_employee()
    assert client.post("/api/dashboard/seed-demo-tickets", headers=emp).status_code == 403
