"""
Comprehensive test suite for AI-Powered Incident Classification (Module 8).
Validates:
- Structured output schema format
- Multiple natural language problem descriptions
- Strict deterministic priority matrix rules (LLM cannot override backend matrix)
- Category to assignment group recommendations
- Graceful fallback when Groq LLM is unavailable or offline
- End-to-end integration with ticket creation API
"""
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
from app.main import app
from app.services.classifier.rules import (
    CATEGORY_ASSIGNMENT_MAP,
    evaluate_priority_matrix,
    normalize_category,
    normalize_level,
    resolve_assignment_group,
)
from app.services.classifier.service import classify_incident_description

client = TestClient(app)


def _login_headers(email: str, password: str) -> Dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_priority_matrix_deterministic_rules():
    """
    Ensure the backend priority engine strictly adheres to the ITIL matrix:
    High x High -> P1 Critical
    High x Medium -> P2 High
    Medium x High -> P2 High
    Medium x Medium -> P3 Medium
    Low x Low -> P4 Low
    """
    assert evaluate_priority_matrix("high", "high") == ("critical", "P1", "P1 Critical")
    assert evaluate_priority_matrix("high", "medium") == ("high", "P2", "P2 High")
    assert evaluate_priority_matrix("medium", "high") == ("high", "P2", "P2 High")
    assert evaluate_priority_matrix("medium", "medium") == ("medium", "P3", "P3 Medium")
    assert evaluate_priority_matrix("low", "low") == ("low", "P4", "P4 Low")
    assert evaluate_priority_matrix("low", "high") == ("medium", "P3", "P3 Medium")


def test_category_and_assignment_recommendations():
    """Verify standard assignment groups correspond to supported incident categories."""
    assert resolve_assignment_group("network") == "Network Support"
    assert resolve_assignment_group("hardware") == "Hardware Support"
    assert resolve_assignment_group("software") == "Software Support"
    assert resolve_assignment_group("security") == "Security Support"
    assert resolve_assignment_group("access_management") == "Access Management"
    assert resolve_assignment_group("email") == "Software Support"
    assert resolve_assignment_group("other") == "Tier 1 Service Desk"


def test_classification_requires_auth():
    resp = client.post("/api/classification/classify", json={"description": "Laptop broken"})
    assert resp.status_code in {401, 403}


def test_classification_rejects_blank():
    headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)
    resp = client.post("/api/classification/classify", json={"description": "   "}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.anyio
@patch("app.services.classifier.service.groq_client.is_configured", return_value=True)
@patch("app.services.classifier.service.groq_client.chat_completion", new_callable=AsyncMock)
async def test_llm_structured_output_example_wifi(mock_groq, mock_is_conf):
    """
    Verify prompt example from Module 8 specification:
    'My company laptop suddenly stopped connecting to Wi-Fi.'
    """
    mock_groq.return_value = """
    {
      "title": "Laptop Wi-Fi connectivity failure",
      "category": "Network",
      "subcategory": "Wi-Fi",
      "impact": "Medium",
      "urgency": "High",
      "recommended_priority": "P2",
      "assignment_group": "Network Support",
      "summary": "Employee cannot connect to corporate Wi-Fi",
      "recommended_action": "Verify network configuration and Wi-Fi adapter driver"
    }
    """
    headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)
    resp = client.post(
        "/api/classification/classify",
        headers=headers,
        json={"description": "My company laptop suddenly stopped connecting to Wi-Fi."},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["title"] == "Laptop Wi-Fi connectivity failure"
    assert data["category"] == "Network"
    assert data["category_value"] == "network"
    assert data["subcategory"] == "Wi-Fi"
    assert data["impact"] == "Medium"
    assert data["urgency"] == "High"
    assert data["recommended_priority"] == "P2"
    assert data["priority_label"] == "P2 High"
    assert data["assignment_group"] == "Network Support"
    assert "Wi-Fi" in data["summary"]
    assert "network" in data["recommended_action"].lower()


@pytest.mark.anyio
@patch("app.services.classifier.service.groq_client.is_configured", return_value=True)
@patch("app.services.classifier.service.groq_client.chat_completion", new_callable=AsyncMock)
async def test_backend_priority_matrix_overrules_hallucinated_llm_priority(mock_groq, mock_is_conf):
    """
    CRITICAL REQUIREMENT:
    'Backend rules must determine final priority. Never let an unvalidated LLM response directly control ticket priority.'
    If the LLM outputs Low impact and Low urgency, but hallucinates 'P1', the backend MUST enforce P4 Low!
    """
    mock_groq.return_value = """
    {
      "title": "Mouse cursor lagging slightly",
      "category": "Hardware",
      "subcategory": "Mouse",
      "impact": "Low",
      "urgency": "Low",
      "recommended_priority": "P1",
      "assignment_group": "Hardware Support",
      "summary": "Single mouse minor lag",
      "recommended_action": "Check USB battery"
    }
    """
    headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)
    resp = client.post(
        "/api/classification/classify",
        headers=headers,
        json={"description": "My optical mouse is lagging a bit on desktop."},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Backend MUST enforce P4 Low based on (Low, Low), ignoring the LLM's hallucinated P1
    assert data["impact"] == "Low"
    assert data["urgency"] == "Low"
    assert data["recommended_priority"] == "P4"
    assert data["priority_label"] == "P4 Low"
    assert data["raw_llm_priority"] == "P1"  # Retained for auditability


@pytest.mark.anyio
async def test_heuristic_fallback_when_groq_unconfigured():
    """
    Ensure classification works reliably even when Groq API key is unconfigured or offline.
    """
    with patch("app.services.classifier.service.groq_client.is_configured", return_value=False):
        headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)

        # 1. Phishing / Security
        sec_res = client.post(
            "/api/classification/classify",
            headers=headers,
            json={"description": "Received a suspicious phishing email asking for corporate credentials urgently."},
        )
        assert sec_res.status_code == 200
        sec_data = sec_res.json()
        assert sec_data["category_value"] == "security"
        assert sec_data["assignment_group"] == "Security Support"

        # 2. VPN failure
        vpn_res = client.post(
            "/api/classification/classify",
            headers=headers,
            json={"description": "GlobalProtect VPN gateway is unreachable error 504 and I am completely blocked."},
        )
        assert vpn_res.status_code == 200
        vpn_data = vpn_res.json()
        assert vpn_data["category_value"] == "network"
        assert vpn_data["assignment_group"] == "Network Support"
        assert vpn_data["urgency"] == "High"

        # 3. YubiKey token setup
        mfa_res = client.post(
            "/api/classification/classify",
            headers=headers,
            json={"description": "Lost my YubiKey hardware token and cannot login to Okta SSO."},
        )
        assert mfa_res.status_code == 200
        mfa_data = mfa_res.json()
        assert mfa_data["category_value"] == "access_management"
        assert mfa_data["assignment_group"] == "Access Management"


@pytest.mark.anyio
@patch("app.services.classifier.service.groq_client.chat_completion", new_callable=AsyncMock)
async def test_e2e_classification_flow_to_ticket_creation(mock_groq):
    """
    End-to-end integration: Employee classifies natural language text,
    then uses structured classification payload to create a real ticket via POST /api/tickets.
    """
    mock_groq.return_value = """
    {
      "title": "Thunderbolt dock second monitor flickering",
      "category": "Hardware",
      "subcategory": "Docking Station",
      "impact": "Medium",
      "urgency": "Medium",
      "recommended_priority": "P3",
      "assignment_group": "Hardware Support",
      "summary": "Dell WD19 dock monitor intermittent blackout",
      "recommended_action": "Power drain dock and test alternate video port"
    }
    """
    headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)
    class_resp = client.post(
        "/api/classification/classify",
        headers=headers,
        json={"description": "My Dell Thunderbolt dock display is flickering black every few minutes."},
    )
    assert class_resp.status_code == 200
    classified = class_resp.json()

    # Verify structured fields
    assert classified["category_value"] == "hardware"
    assert classified["subcategory"] == "Docking Station"
    assert classified["recommended_priority"] == "P3"

    # Now create real ticket using classification fields
    ticket_payload = {
        "title": classified["title"],
        "description": f"{classified['summary']}\nRecommended Action: {classified['recommended_action']}",
        "category": classified["category_value"],
        "subcategory": classified["subcategory"],
        "impact": classified["impact_value"],
        "urgency": classified["urgency_value"],
    }
    create_resp = client.post("/api/tickets", headers=headers, json=ticket_payload)
    assert create_resp.status_code == 201, create_resp.text
    ticket = create_resp.json()

    assert ticket["ticket_number"].startswith("INC")
    assert ticket["title"] == classified["title"]
    assert ticket["category"] == "hardware"
    assert ticket["priority"] == "medium"
    assert ticket["priority_label"] == "P3 Medium"
    assert ticket["sla_deadline"] is not None
