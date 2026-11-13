from typing import Dict
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database.init_db import (
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_PASSWORD,
    DEMO_EMPLOYEE_EMAIL,
    DEMO_EMPLOYEE_PASSWORD,
)
from app.database.session import get_db
from app.main import app
from app.models.agent import AgentEscalation, AgentToolLog
from app.models.audit_log import AuditLog
from app.models.ticket import Ticket, TicketHistory
from app.models.user import User
from app.services.agent.tools import (
    AgentSafetyError,
    execute_agent_tool,
)

client = TestClient(app)


def _login_headers(email: str, password: str) -> Dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _register_second_employee() -> Dict[str, str]:
    email = "second.employee@nexdesk.ai"
    client.post(
        "/api/auth/register",
        json={"name": "Second Employee", "email": email, "password": "Password123!"},
    )
    return _login_headers(email, "Password123!")


def test_list_available_agent_tools():
    headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)
    resp = client.get("/api/agent/tools", headers=headers)
    assert resp.status_code == 200
    tool_names = {t["name"] for t in resp.json()["tools"]}
    expected = {
        "search_knowledge_base",
        "classify_incident",
        "recommend_priority",
        "recommend_assignment_group",
        "get_ticket_status",
        "prepare_ticket",
        "create_ticket_after_confirmation",
        "escalate_to_human",
    }
    assert expected.issubset(tool_names)


def test_independent_agent_tools_and_safety_guardrails():
    db = next(app.dependency_overrides[get_db]())
    try:
        emp = db.query(User).filter(User.email == DEMO_EMPLOYEE_EMAIL).first()
        assert emp is not None

        # 1. classify_incident
        cls_res = execute_agent_tool(
            db,
            emp,
            "classify_incident",
            {"description": "My company laptop suddenly stopped connecting to Wi-Fi."},
        )
        assert cls_res["status"] == "success"
        assert cls_res["result"]["category_value"] == "network"

        # 2. recommend_priority
        prio_res = execute_agent_tool(
            db,
            emp,
            "recommend_priority",
            {"impact": "medium", "urgency": "high"},
        )
        assert prio_res["result"]["recommended_priority"] == "P2"

        # 3. recommend_assignment_group
        grp_res = execute_agent_tool(
            db,
            emp,
            "recommend_assignment_group",
            {"category": "network"},
        )
        assert grp_res["result"]["assignment_group"] == "Network Support"
        assert grp_res["result"]["group_id"] is not None

        # 4. Forbidden auto-close tool must be blocked and logged
        with pytest.raises(AgentSafetyError):
            execute_agent_tool(db, emp, "close_ticket", {"ticket_id": 1})

        blocked_log = (
            db.query(AgentToolLog)
            .filter(AgentToolLog.tool_name == "close_ticket", AgentToolLog.status == "blocked")
            .first()
        )
        assert blocked_log is not None
    finally:
        db.close()


@pytest.mark.anyio
@patch("app.api.routes.chat.groq_client.chat_completion", new_callable=AsyncMock)
async def test_full_employee_to_technician_hitl_workflow(mock_chat):
    emp_headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)
    admin_headers = _login_headers(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
    second_emp_headers = _register_second_employee()

    db = next(app.dependency_overrides[get_db]())
    try:
        initial_ticket_count = db.query(Ticket).count()
    finally:
        db.close()

    # Turn 1: Initial VPN issue -> troubleshooting instructions (no ticket prepared yet)
    mock_chat.return_value = (
        "Let's troubleshoot your VPN connection:\n"
        "1. Flush your DNS cache using ipconfig /flushdns.\n"
        "2. Sign out of cached GlobalProtect credentials and reconnect to vpn-east.nexdesk.ai."
    )
    turn1 = client.post(
        "/api/chat",
        headers=emp_headers,
        json={"message": "My VPN is not connecting"},
    )
    assert turn1.status_code == 200, turn1.text
    t1_data = turn1.json()
    conv_id = t1_data["conversation_id"]
    assert t1_data["pending_action"] is None
    assert {tc["tool_name"] for tc in t1_data["tool_calls"]} >= {
        "search_knowledge_base",
        "classify_incident",
        "recommend_priority",
        "recommend_assignment_group",
    }

    # Turn 2: Employee reports troubleshooting failed -> prepares ticket & asks confirmation
    mock_chat.return_value = (
        "Since the initial VPN troubleshooting steps did not resolve the issue, I have prepared an IT support "
        "ticket for Network Support. Please review the preview card below and confirm creation."
    )
    turn2 = client.post(
        "/api/chat",
        headers=emp_headers,
        json={
            "conversation_id": conv_id,
            "message": "My VPN is still not working after following the instructions.",
        },
    )
    assert turn2.status_code == 200, turn2.text
    t2_data = turn2.json()
    assert t2_data["conversation_id"] == conv_id
    pending = t2_data["pending_action"]
    assert pending is not None
    assert pending["status"] == "pending_confirmation"
    assert pending["category_value"] == "network"
    assert pending["assignment_group"] == "Network Support"
    assert pending["recommended_priority"] in {"P1", "P2", "P3"}
    assert len(pending["attempted_troubleshooting"]) >= 1
    assert any(tc["tool_name"] == "prepare_ticket" for tc in t2_data["tool_calls"])

    # CRITICAL SAFETY CHECK: Zero tickets created before human confirmation!
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.query(Ticket).count() == initial_ticket_count
    finally:
        db.close()

    confirmation_id = pending["confirmation_id"]

    # Safety: Another employee cannot confirm this user's pending action
    unauth_confirm = client.post(
        "/api/agent/confirm",
        headers=second_emp_headers,
        json={"confirmation_id": confirmation_id},
    )
    assert unauth_confirm.status_code == 403

    # Turn 3: Employee confirms creation via HITL confirmation endpoint
    confirm_res = client.post(
        "/api/agent/confirm",
        headers=emp_headers,
        json={
            "confirmation_id": confirmation_id,
            "title": "VPN tunnel still failing after DNS flush",
            "escalate_to_human": True,
        },
    )
    assert confirm_res.status_code == 201, confirm_res.text
    c_data = confirm_res.json()
    assert c_data["status"] == "confirmed"
    ticket = c_data["ticket"]
    assert ticket["ticket_number"].startswith("INC")
    assert ticket["assigned_group"] == "Network Support"
    assert ticket["status"] == "assigned"
    assert c_data["escalation"] is not None
    assert c_data["escalation"]["recommended_group_name"] == "Network Support"
    assert len(c_data["escalation"]["attempted_troubleshooting"]) >= 1

    ticket_id = ticket["id"]
    ticket_number = ticket["ticket_number"]

    # Safety: Duplicate confirmation blocked -> 409 Conflict & no second ticket created
    dup_confirm = client.post(
        "/api/agent/confirm",
        headers=emp_headers,
        json={"confirmation_id": confirmation_id},
    )
    assert dup_confirm.status_code == 409

    # Verify get_ticket_status tool works for the newly created ticket via chat
    mock_chat.return_value = f"Your ticket {ticket_number} is currently assigned to Network Support."
    turn4 = client.post(
        "/api/chat",
        headers=emp_headers,
        json={
            "conversation_id": conv_id,
            "message": f"What is the ticket status for {ticket_number}?",
        },
    )
    assert turn4.status_code == 200
    assert any(tc["tool_name"] == "get_ticket_status" for tc in turn4.json()["tool_calls"])

    # Verify escalations list endpoint (ownership scoped)
    emp_escs = client.get(f"/api/agent/escalations?ticket_id={ticket_id}", headers=emp_headers)
    assert emp_escs.status_code == 200
    assert len(emp_escs.json()) == 1
    assert emp_escs.json()[0]["ticket_number"] == ticket_number

    other_escs = client.get(f"/api/agent/escalations?ticket_id={ticket_id}", headers=second_emp_headers)
    assert other_escs.status_code == 200
    assert other_escs.json() == []

    # Admin overrides AI recommendation (switches impact/urgency & group with reason)
    emp_override_attempt = client.post(
        f"/api/agent/tickets/{ticket_id}/override",
        headers=emp_headers,
        json={"assignment_group": "Security Support", "override_reason": "Trying unauthorized override"},
    )
    assert emp_override_attempt.status_code == 403

    admin_override = client.post(
        f"/api/agent/tickets/{ticket_id}/override",
        headers=admin_headers,
        json={
            "category": "security",
            "impact": "high",
            "urgency": "high",
            "assignment_group": "Security Support",
            "override_reason": "Certificate failure indicates possible endpoint security policy block.",
        },
    )
    assert admin_override.status_code == 200, admin_override.text
    overridden_ticket = admin_override.json()["ticket"]
    assert overridden_ticket["priority"] == "critical"
    assert overridden_ticket["priority_label"] == "P1 Critical"
    assert overridden_ticket["assigned_group"] == "Security Support"

    # Verify tool logs & audit logs recorded
    logs_res = client.get("/api/agent/logs", headers=emp_headers)
    assert logs_res.status_code == 200
    assert logs_res.json()["total"] >= 5

    db = next(app.dependency_overrides[get_db]())
    try:
        override_audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "ADMIN_OVERRIDE_AI_RECOMMENDATION",
                AuditLog.resource_id == str(ticket_id),
            )
            .first()
        )
        assert override_audit is not None
        assert db.query(TicketHistory).filter(TicketHistory.ticket_id == ticket_id).count() >= 3
    finally:
        db.close()


def test_direct_prepare_cancel_and_escalate_endpoints():
    headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)

    prep = client.post(
        "/api/agent/prepare-ticket",
        headers=headers,
        json={
            "description": "Outlook desktop freezes whenever opening calendar invites.",
            "attempted_troubleshooting": ["Cleared Outlook cache", "Restarted in safe mode"],
        },
    )
    assert prep.status_code == 200, prep.text
    conf_id = prep.json()["confirmation_id"]
    assert prep.json()["assignment_group"] == "Software Support"

    # Cancel prevents subsequent confirmation
    cancel = client.post("/api/agent/cancel", headers=headers, json={"confirmation_id": conf_id})
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    confirm_cancelled = client.post(
        "/api/agent/confirm",
        headers=headers,
        json={"confirmation_id": conf_id},
    )
    assert confirm_cancelled.status_code == 422

    # Direct human escalation standalone record
    esc = client.post(
        "/api/agent/escalate",
        headers=headers,
        json={
            "reason": "Okta MFA hardware key lost and needs manual bypass code.",
            "attempted_troubleshooting": ["Attempted recovery backup code"],
        },
    )
    assert esc.status_code == 201, esc.text
    assert esc.json()["recommended_group_name"] == "Access Management"
    assert esc.json()["attempted_troubleshooting"] == ["Attempted recovery backup code"]
