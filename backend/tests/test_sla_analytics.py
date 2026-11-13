"""
Unit and integration tests for Module 10: SLA Management and Service Analytics.
Tests calendar vs business hours calculation, ticket age, breach evaluation,
KPI analytics, trends, distributions, workload, and SLA policy CRUD.
"""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.assignment_group import AssignmentGroup
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.user import User
from app.services.sla.calculator import (
    calculate_business_deadline,
    calculate_calendar_deadline,
    calculate_ticket_age,
    compute_deadlines,
    evaluate_ticket_sla_status,
    format_duration,
)

client = TestClient(app)


def _login(email: str, password: str):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth_headers() -> dict:
    return _login("admin@nexdesk.ai", "AdminPassword123!")


@pytest.fixture
def employee_headers() -> dict:
    return _login("employee@nexdesk.ai", "EmployeePassword123!")


# -----------------------------------------------------------------------------
# 1. Unit Tests for SLA Calculator
# -----------------------------------------------------------------------------

def test_calendar_deadline_calculation():
    start = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    # 15 minutes
    dl_15 = calculate_calendar_deadline(start, 15)
    assert dl_15 == datetime(2026, 11, 10, 10, 15, 0, tzinfo=timezone.utc)

    # 4 hours (240 minutes)
    dl_4h = calculate_calendar_deadline(start, 240)
    assert dl_4h == datetime(2026, 11, 10, 14, 0, 0, tzinfo=timezone.utc)


def test_business_deadline_calculation_same_day():
    # Tuesday 10:00 AM UTC, 120 minutes (2 hours) -> Tuesday 12:00 PM UTC
    tuesday_10am = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    dl = calculate_business_deadline(tuesday_10am, 120)
    assert dl == datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)


def test_business_deadline_rolls_over_night():
    # Tuesday 4:00 PM UTC (16:00), 120 minutes:
    # 60 mins until 17:00, remaining 60 mins next day 09:00 -> Wednesday 10:00 AM UTC
    tuesday_4pm = datetime(2026, 11, 10, 16, 0, 0, tzinfo=timezone.utc)
    dl = calculate_business_deadline(tuesday_4pm, 120)
    assert dl == datetime(2026, 11, 11, 10, 0, 0, tzinfo=timezone.utc)


def test_business_deadline_skips_weekends():
    # Friday 3:30 PM UTC (15:30), 240 minutes (4 hours):
    # 90 minutes remaining on Friday until 17:00.
    # 150 minutes remaining -> resumes Monday 09:00 + 2h30m -> Monday 11:30 AM UTC
    # 2026-11-13 is a Friday, 2026-11-16 is Monday.
    friday_330pm = datetime(2026, 11, 13, 15, 30, 0, tzinfo=timezone.utc)
    dl = calculate_business_deadline(friday_330pm, 240)
    assert dl == datetime(2026, 11, 16, 11, 30, 0, tzinfo=timezone.utc)


def test_ticket_age_and_duration_formatting():
    assert format_duration(45 * 60) == "45m"
    assert format_duration(3 * 3600 + 20 * 60) == "3h 20m"
    assert format_duration(2 * 86400 + 5 * 3600) == "2d 5h"

    start = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 10, 12, 30, 0, tzinfo=timezone.utc)
    age = calculate_ticket_age(start, end)
    assert age["hours"] == 2.5
    assert age["display"] == "2h 30m"


def test_evaluate_ticket_sla_status_compliant():
    now = datetime(2026, 11, 10, 11, 0, 0, tzinfo=timezone.utc)
    ticket = Ticket(
        created_at=datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
        response_deadline=datetime(2026, 11, 10, 10, 30, 0, tzinfo=timezone.utc),
        first_responded_at=datetime(2026, 11, 10, 10, 15, 0, tzinfo=timezone.utc),
        sla_deadline=datetime(2026, 11, 10, 18, 0, 0, tzinfo=timezone.utc),
        status="in_progress",
    )
    status_info = evaluate_ticket_sla_status(ticket, as_of=now)
    assert status_info["is_compliant"] is True
    assert status_info["response_breached"] is False
    assert status_info["resolution_breached"] is False
    assert status_info["is_overdue"] is False
    assert status_info["sla_status"] == "compliant"


def test_evaluate_ticket_sla_status_overdue():
    now = datetime(2026, 11, 10, 19, 0, 0, tzinfo=timezone.utc)
    ticket = Ticket(
        created_at=datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
        response_deadline=datetime(2026, 11, 10, 10, 30, 0, tzinfo=timezone.utc),
        first_responded_at=datetime(2026, 11, 10, 10, 15, 0, tzinfo=timezone.utc),
        sla_deadline=datetime(2026, 11, 10, 18, 0, 0, tzinfo=timezone.utc),
        status="open",
    )
    status_info = evaluate_ticket_sla_status(ticket, as_of=now)
    assert status_info["is_compliant"] is False
    assert status_info["resolution_breached"] is True
    assert status_info["is_overdue"] is True
    assert status_info["sla_status"] in ("resolution_breached", "both_breached")


# -----------------------------------------------------------------------------
# 2. Integration Tests for Analytics and SLA Endpoints
# -----------------------------------------------------------------------------

def test_analytics_summary_endpoint(auth_headers: dict):
    res = client.get("/api/analytics/summary?range=30d", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_tickets" in data
    assert "open_tickets" in data
    assert "in_progress_tickets" in data
    assert "resolved_tickets" in data
    assert "sla_breaches" in data
    assert "avg_resolution_time_hours" in data
    assert "avg_resolution_time_display" in data
    assert "sla_compliance_rate" in data
    assert "response_compliance_rate" in data
    assert "resolution_compliance_rate" in data
    assert data["date_range"] == "30d"


def test_analytics_ticket_trends_endpoint(auth_headers: dict):
    res = client.get("/api/analytics/ticket-trends?range=7d", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        assert "date" in data[0]
        assert "created" in data[0]
        assert "resolved" in data[0]
        assert "breached" in data[0]


def test_analytics_distributions_endpoints(auth_headers: dict):
    # Category
    cat_res = client.get("/api/analytics/category-distribution?range=30d", headers=auth_headers)
    assert cat_res.status_code == 200
    cats = cat_res.json()
    assert isinstance(cats, list)
    assert len(cats) >= 7

    # Priority
    pri_res = client.get("/api/analytics/priority-distribution?range=30d", headers=auth_headers)
    assert pri_res.status_code == 200
    pris = pri_res.json()
    assert len(pris) == 4
    priorities = [p["priority"] for p in pris]
    assert priorities == ["critical", "high", "medium", "low"]

    # Status
    stat_res = client.get("/api/analytics/status-distribution?range=30d", headers=auth_headers)
    assert stat_res.status_code == 200
    stats = stat_res.json()
    assert isinstance(stats, list)

    # Workload
    work_res = client.get("/api/analytics/workload?range=30d", headers=auth_headers)
    assert work_res.status_code == 200
    workload = work_res.json()
    assert isinstance(workload, list)


def test_sla_overview_endpoint(auth_headers: dict):
    res = client.get("/api/sla/overview", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_evaluated" in data
    assert "total_breached" in data
    assert "total_overdue" in data
    assert "overall_compliance_rate" in data
    assert "policies" in data
    assert isinstance(data["policies"], list)
    assert "overdue_incidents" in data
    assert "recent_breaches" in data


def test_sla_policies_crud(auth_headers: dict, employee_headers: dict):
    # List policies
    list_res = client.get("/api/sla/policies", headers=auth_headers)
    assert list_res.status_code == 200
    policies = list_res.json()
    assert len(policies) >= 4

    # Non-admin cannot create policy
    fail_create = client.post(
        "/api/sla/policies",
        json={
            "name": "Unauthorized Policy",
            "priority": "low",
            "response_time_minutes": 60,
            "resolution_time_hours": 12,
        },
        headers=employee_headers,
    )
    assert fail_create.status_code == 403

    # Admin creates policy
    create_res = client.post(
        "/api/sla/policies",
        json={
            "name": "Custom VIP Critical",
            "priority": "critical",
            "response_time_minutes": 10,
            "resolution_time_hours": 2,
            "business_hours_only": False,
            "escalation_contact": "vip-leads@nexdesk.ai",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    # Admin updates policy
    update_res = client.put(
        f"/api/sla/policies/{created_id}",
        json={"name": "Custom VIP Critical Updated", "resolution_time_hours": 3},
        headers=auth_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Custom VIP Critical Updated"
    assert update_res.json()["resolution_time_hours"] == 3

    # Admin deletes policy
    del_res = client.delete(f"/api/sla/policies/{created_id}", headers=auth_headers)
    assert del_res.status_code == 200
