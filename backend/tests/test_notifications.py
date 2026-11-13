import smtplib
from unittest.mock import MagicMock, patch
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.init_db import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD
from app.main import app
from app.models.notification import EmailDeliveryLog, Notification
from app.models.ticket import Ticket
from app.models.user import User
from app.services.notifications.email_service import send_email
from app.services.notifications.notification_service import notify_ticket_submitted
from tests.conftest import TestingSessionLocal

client = TestClient(app)


def _login(email: str, password: str):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


def _register_and_login(name: str = "Notification Employee"):
    email = f"notif_{uuid.uuid4().hex[:8]}@nexdesk.ai"
    pw = "StrongPassword123!"
    reg = client.post("/api/auth/register", json={"name": name, "email": email, "password": pw})
    assert reg.status_code == 201, reg.text
    db = TestingSessionLocal()
    try:
        from app.models.user import User
        u = db.query(User).filter(User.email == email).first()
        if u:
            u.email_verified = True
            db.commit()
    finally:
        db.close()
    headers, user = _login(email, pw)
    return headers, user, email


def _ticket_payload(**overrides):
    data = {
        "title": f"VPN connectivity failure {uuid.uuid4().hex[:6]}",
        "description": "GlobalProtect VPN hangs on authentication from home network.",
        "category": "network",
        "subcategory": "VPN",
        "impact": "high",
        "urgency": "high",
    }
    data.update(overrides)
    return data


def test_unauthorized_notification_endpoints_rejected():
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401
    assert client.patch("/api/notifications/1/read").status_code == 401
    assert client.patch("/api/notifications/read-all").status_code == 401
    assert client.get("/api/notifications/email-history").status_code == 401
    assert client.get("/api/notifications/config").status_code == 401


def test_employee_and_admin_notifications_and_dynamic_recipient_routing(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.mock.local")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "smtp_user_secret")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "super_secret_pw")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@nexdesk.ai")
    monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAIL", "bb7578167@gmail.com")

    emp_a_headers, emp_a_user, emp_a_email = _register_and_login("Employee Alpha")
    emp_b_headers, emp_b_user, emp_b_email = _register_and_login("Employee Beta")
    admin_headers, _ = _login(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)

    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=10):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            return None

        def login(self, username, password):
            return None

        def send_message(self, msg):
            sent_messages.append({"to": msg["To"], "subject": msg["Subject"], "body": msg.get_body(preferencelist=("html",)).get_content()})

    with patch("app.services.notifications.email_service.smtplib.SMTP", FakeSMTP):
        # Employee A creates ticket
        t_a = client.post("/api/tickets", json=_ticket_payload(title="Alpha VPN outage"), headers=emp_a_headers)
        assert t_a.status_code == 201, t_a.text
        ticket_a = t_a.json()

        # Employee B creates ticket
        t_b = client.post("/api/tickets", json=_ticket_payload(title="Beta laptop Wi-Fi issue"), headers=emp_b_headers)
        assert t_b.status_code == 201, t_b.text
        ticket_b = t_b.json()

    # Employee A only sees Employee A notifications and email logs
    a_notifs = client.get("/api/notifications", headers=emp_a_headers).json()
    assert a_notifs["unread_count"] == 1
    assert any(n["ticket_number"] == ticket_a["ticket_number"] and n["notification_type"] == "ticket_submitted" for n in a_notifs["items"])
    assert not any(n["ticket_number"] == ticket_b["ticket_number"] for n in a_notifs["items"])

    # Employee B receives notifications at Employee B's email and only sees B's notifications
    b_notifs = client.get("/api/notifications", headers=emp_b_headers).json()
    assert b_notifs["unread_count"] == 1
    assert any(n["ticket_number"] == ticket_b["ticket_number"] for n in b_notifs["items"])
    assert not any(n["ticket_number"] == ticket_a["ticket_number"] for n in b_notifs["items"])

    # Admin received new incident alerts for both tickets
    admin_notifs = client.get("/api/notifications", headers=admin_headers).json()
    assert any(
        n["ticket_number"] == ticket_a["ticket_number"]
        and n["notification_type"] == "new_incident_alert"
        and "Employee Alpha" in n["message"]
        for n in admin_notifs["items"]
    )

    # Verify outbound emails targeted Employee A email, Employee B email, and fixed Admin email bb7578167@gmail.com
    recipients_for_a = [m["to"] for m in sent_messages if ticket_a["ticket_number"] in m["subject"]]
    recipients_for_b = [m["to"] for m in sent_messages if ticket_b["ticket_number"] in m["subject"]]
    assert emp_a_email in recipients_for_a
    assert "bb7578167@gmail.com" in recipients_for_a
    assert emp_b_email in recipients_for_b
    assert "bb7578167@gmail.com" in recipients_for_b

    # Verify EmailDeliveryLog tracks recipient_verified accurately (A verified=True, B verified=False)
    a_logs = client.get(f"/api/notifications/email-history?ticket_id={ticket_a['id']}", headers=emp_a_headers).json()
    assert len(a_logs) == 1
    assert a_logs[0]["recipient_email"] == emp_a_email
    assert a_logs[0]["recipient_verified"] is True
    assert a_logs[0]["delivery_status"] == "sent"

    b_logs = client.get(f"/api/notifications/email-history?ticket_id={ticket_b['id']}", headers=emp_b_headers).json()
    assert len(b_logs) == 1
    assert b_logs[0]["recipient_email"] == emp_b_email
    assert b_logs[0]["recipient_verified"] is True
    assert b_logs[0]["delivery_status"] == "sent"

    # Security: Employee A cannot read/mark Employee B's notification or access B's email history or admin config
    b_notif_id = b_notifs["items"][0]["id"]
    assert client.patch(f"/api/notifications/{b_notif_id}/read", headers=emp_a_headers).status_code == 403
    assert client.get(f"/api/notifications/email-history?ticket_id={ticket_b['id']}", headers=emp_a_headers).status_code == 404
    assert client.get("/api/notifications/config", headers=emp_a_headers).status_code == 403

    # Admin config returns sanitized admin notification email without exposing secrets
    cfg = client.get("/api/notifications/config", headers=admin_headers).json()
    assert cfg["admin_notification_email"] == "bb7578167@gmail.com"
    assert "smtp_password" not in cfg
    assert "super_secret_pw" not in str(cfg)


def test_read_mark_all_and_duplicate_idempotency(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    emp_headers, _, emp_email = _register_and_login("Idempotency User")

    t1 = client.post("/api/tickets", json=_ticket_payload(title="Ticket One"), headers=emp_headers).json()
    t2 = client.post("/api/tickets", json=_ticket_payload(title="Ticket Two"), headers=emp_headers).json()

    assert client.get("/api/notifications/unread-count", headers=emp_headers).json()["unread_count"] == 2

    # Replay notify_ticket_submitted repeatedly: duplicate notifications and emails must not be created
    db = TestingSessionLocal()
    try:
        ticket_obj = db.query(Ticket).filter(Ticket.id == t1["id"]).first()
        user_obj = db.query(User).filter(User.email == emp_email).first()
        notify_ticket_submitted(db, ticket_obj, user_obj)
        notify_ticket_submitted(db, ticket_obj, user_obj)
        notif_count = (
            db.query(Notification)
            .filter(Notification.ticket_id == t1["id"], Notification.recipient_user_id == user_obj.id)
            .count()
        )
        email_count = (
            db.query(EmailDeliveryLog)
            .filter(EmailDeliveryLog.ticket_id == t1["id"], EmailDeliveryLog.recipient_email == emp_email)
            .count()
        )
        assert notif_count == 1
        assert email_count == 1
    finally:
        db.close()

    # Mark single notification read
    items = client.get("/api/notifications", headers=emp_headers).json()["items"]
    first_id = items[0]["id"]
    mark_res = client.patch(f"/api/notifications/{first_id}/read", headers=emp_headers)
    assert mark_res.status_code == 200
    assert mark_res.json()["is_read"] is True
    assert client.get("/api/notifications/unread-count", headers=emp_headers).json()["unread_count"] == 1

    # Mark all remaining notifications read
    read_all = client.patch("/api/notifications/read-all", headers=emp_headers)
    assert read_all.status_code == 200
    assert read_all.json()["marked_count"] == 1
    assert client.get("/api/notifications/unread-count", headers=emp_headers).json()["unread_count"] == 0


def test_smtp_failure_does_not_rollback_ticket_or_leak_secrets(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.broken.local")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "secret_user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "ultra_secret_password_99")
    monkeypatch.setattr(settings, "SMTP_MAX_RETRIES", 2)

    emp_headers, _, emp_email = _register_and_login("Resilience Tester")

    failing_smtp = MagicMock(side_effect=smtplib.SMTPAuthenticationError(535, b"Auth failed ultra_secret_password_99"))
    with patch("app.services.notifications.email_service.smtplib.SMTP", failing_smtp):
        r = client.post("/api/tickets", json=_ticket_payload(title="Ticket persists on SMTP fail"), headers=emp_headers)
        assert r.status_code == 201, r.text
        ticket = r.json()

    # Ticket was committed cleanly despite SMTP failure
    get_res = client.get(f"/api/tickets/{ticket['id']}", headers=emp_headers)
    assert get_res.status_code == 200
    assert get_res.json()["ticket_number"] == ticket["ticket_number"]

    # In-app notification still exists
    notifs = client.get(f"/api/notifications?ticket_id={ticket['id']}", headers=emp_headers).json()
    assert len(notifs["items"]) == 1

    # EmailDeliveryLog recorded failure with retry attempt count and redacted password
    logs = client.get(f"/api/notifications/email-history?ticket_id={ticket['id']}", headers=emp_headers).json()
    assert len(logs) == 1
    assert logs[0]["delivery_status"] == "failed"
    assert logs[0]["attempt_count"] == 2
    assert "ultra_secret_password_99" not in (logs[0]["error_message"] or "")
    assert "[REDACTED]" in (logs[0]["error_message"] or "")


def test_unconfigured_smtp_and_recipient_validation(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    emp_headers, _, _ = _register_and_login("NoSMTP User")

    r = client.post("/api/tickets", json=_ticket_payload(title="Unconfigured SMTP ticket"), headers=emp_headers)
    assert r.status_code == 201
    ticket = r.json()

    logs = client.get(f"/api/notifications/email-history?ticket_id={ticket['id']}", headers=emp_headers).json()
    assert len(logs) == 1
    assert logs[0]["delivery_status"] == "skipped_unconfigured"

    # Reject invalid email addresses cleanly on backend
    db = TestingSessionLocal()
    try:
        bad_log = send_email(
            db,
            recipient_email="invalid-address\r\nBcc:evil@attacker.com",
            subject="Subject",
            html_body="<p>Hi</p>",
            text_body="Hi",
            event_type="test",
            event_key=f"invalid-test-{uuid.uuid4().hex}",
        )
        assert bad_log.delivery_status == "failed"
    finally:
        db.close()


def test_e2e_13_step_acceptance_scenario(monkeypatch):
    """Verify full 13-step employee submission -> admin triage/assign/status/resolve -> employee notifications workflow."""
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.e2e.local")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "mock_password")
    monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAIL", "bb7578167@gmail.com")

    emp_headers, emp_user, emp_email = _register_and_login("Acceptance Employee")
    admin_headers, _ = _login(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)

    groups = client.get("/api/assignment-groups", headers=admin_headers).json()
    network_group = next((g for g in groups if "network" in g["name"].lower()), groups[0])

    dispatched = []

    class RecordingSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            return None

        def login(self, u, p):
            return None

        def send_message(self, msg):
            dispatched.append((msg["To"], msg["Subject"]))

    with patch("app.services.notifications.email_service.smtplib.SMTP", RecordingSMTP):
        # 2-4. Employee creates VPN ticket and sees submission confirmation
        create_res = client.post(
            "/api/tickets",
            json=_ticket_payload(title="My VPN is failing after password rotation"),
            headers=emp_headers,
        )
        assert create_res.status_code == 201
        ticket = create_res.json()
        tid = ticket["id"]
        tnum = ticket["ticket_number"]

        emp_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=emp_headers).json()["items"]
        assert any(n["notification_type"] == "ticket_submitted" and tnum in n["title"] for n in emp_notifs)

        # 5. Admin receives new-ticket notification
        admin_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=admin_headers).json()["items"]
        assert any(n["notification_type"] == "new_incident_alert" and tnum in n["title"] for n in admin_notifs)

        # 6-7. Admin assigns Network Support -> employee sees assignment update
        assign_res = client.patch(
            f"/api/tickets/{tid}",
            json={"group_id": network_group["id"]},
            headers=admin_headers,
        )
        assert assign_res.status_code == 200
        assert assign_res.json()["assigned_group"] == network_group["name"]

        emp_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=emp_headers).json()["items"]
        assert any(
            n["notification_type"] == "ticket_assigned" and network_group["name"] in n["message"]
            for n in emp_notifs
        )

        # Minor non-status field edit (subcategory) must NOT emit unnecessary email
        emails_before_minor = len(dispatched)
        minor_res = client.patch(
            f"/api/tickets/{tid}",
            json={"subcategory": "GlobalProtect Gateway"},
            headers=admin_headers,
        )
        assert minor_res.status_code == 200
        assert len(dispatched) == emails_before_minor

        # 8-9. Admin changes status to In Progress -> employee receives status notification
        prog_res = client.patch(
            f"/api/tickets/{tid}",
            json={"status": "in_progress"},
            headers=admin_headers,
        )
        assert prog_res.status_code == 200
        emp_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=emp_headers).json()["items"]
        assert any(
            n["notification_type"] == "ticket_status_updated" and "In Progress" in n["title"]
            for n in emp_notifs
        )

        # 10-12. Admin resolves ticket with resolution notes -> employee receives resolution notification & opens details
        notes = "Reset user VPN gateway token and flushed stale Okta session."
        resolve_res = client.patch(
            f"/api/tickets/{tid}",
            json={"status": "resolved", "resolution_notes": notes},
            headers=admin_headers,
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "resolved"  # Not auto-closed

        emp_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=emp_headers).json()["items"]
        assert any(
            n["notification_type"] == "ticket_resolved" and notes in n["message"]
            for n in emp_notifs
        )

        emp_ticket = client.get(f"/api/tickets/{tid}", headers=emp_headers).json()
        assert emp_ticket["resolution_notes"] == notes
        assert emp_ticket["resolved_at"] is not None

        # 13. Administrator sees resolved incident & recent notifications in dashboard stats
        dash = client.get("/api/dashboard/stats", headers=admin_headers).json()
        assert any(t["id"] == tid for t in dash["recently_resolved_incidents"])
        assert len(dash["recent_notifications"]) > 0

        # Confirm emails sent to employee email and admin email across lifecycle
        assert any(to == emp_email and "Resolved" in subj for to, subj in dispatched)
        assert any(to == "bb7578167@gmail.com" and "Resolved" in subj for to, subj in dispatched)


def test_registration_comments_priority_closure_and_sla_notifications(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAIL", "bb7578167@gmail.com")
    monkeypatch.setattr(settings, "ADMIN_EMAIL", "bb7578167@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    admin_headers, _ = _login(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
    emp_headers, emp_user, emp_email = _register_and_login("Alert Employee")
    other_headers, _, _ = _register_and_login("Other Employee")

    # 1. Registration notified admins
    admin_notifs = client.get("/api/notifications?limit=100", headers=admin_headers).json()["items"]
    assert any(
        n["notification_type"] == "user_registered" and emp_email in n["message"]
        for n in admin_notifs
    )

    # 2. Critical priority ticket (impact=high + urgency=high) triggers employee + admin + high_priority_alert
    create_res = client.post(
        "/api/tickets",
        json=_ticket_payload(
            title="Core production firewall outage",
            impact="high",
            urgency="high",
        ),
        headers=emp_headers,
    )
    assert create_res.status_code == 201, create_res.text
    ticket = create_res.json()
    tid = ticket["id"]
    assert ticket["priority"] == "critical"

    emp_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=emp_headers).json()["items"]
    assert any(n["notification_type"] == "ticket_submitted" for n in emp_notifs)

    admin_ticket_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=admin_headers).json()["items"]
    admin_types = {n["notification_type"] for n in admin_ticket_notifs}
    assert "new_incident_alert" in admin_types
    assert "high_priority_alert" in admin_types

    # 3. Employee reply notifies admins; Admin comment notifies employee; cross-employee access blocked
    reply_res = client.post(
        f"/api/tickets/{tid}/comments",
        json={"message": "We tested from two office subnets and both timed out."},
        headers=emp_headers,
    )
    assert reply_res.status_code == 201, reply_res.text
    assert reply_res.json()["author_role"] == "employee"

    assert (
        client.get(f"/api/tickets/{tid}/comments", headers=other_headers).status_code == 404
    )
    assert (
        client.post(
            f"/api/tickets/{tid}/comments",
            json={"message": "Unauthorized peek"},
            headers=other_headers,
        ).status_code == 404
    )

    admin_ticket_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=admin_headers).json()["items"]
    assert any(n["notification_type"] == "employee_reply" for n in admin_ticket_notifs)

    admin_comment_res = client.post(
        f"/api/tickets/{tid}/comments",
        json={"message": "Network team captured packet trace and is updating ACL rules."},
        headers=admin_headers,
    )
    assert admin_comment_res.status_code == 201, admin_comment_res.text
    assert admin_comment_res.json()["author_role"] == "admin"

    emp_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=emp_headers).json()["items"]
    assert any(
        n["notification_type"] == "admin_comment" and "updating ACL rules" in n["message"]
        for n in emp_notifs
    )

    comments_list = client.get(f"/api/tickets/{tid}/comments", headers=emp_headers).json()
    assert len(comments_list) == 2

    # 4. Admin closure creates ticket_closed for both employee and admin
    close_res = client.patch(
        f"/api/tickets/{tid}",
        json={"status": "closed", "resolution_notes": "Confirmed firewall ACL restored."},
        headers=admin_headers,
    )
    assert close_res.status_code == 200
    emp_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=emp_headers).json()["items"]
    admin_ticket_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=admin_headers).json()["items"]
    assert any(n["notification_type"] == "ticket_closed" for n in emp_notifs)
    assert any(n["notification_type"] == "ticket_closed" for n in admin_ticket_notifs)

    # 5. Priority escalation notifies both employee and admins; SLA breach notifies admins idempotently
    from datetime import datetime, timedelta, timezone

    sla_ticket_res = client.post(
        "/api/tickets",
        json=_ticket_payload(title="SLA Breach Monitoring Ticket", impact="low", urgency="low"),
        headers=emp_headers,
    )
    assert sla_ticket_res.status_code == 201, sla_ticket_res.text
    sla_tid = sla_ticket_res.json()["id"]

    esc_res = client.patch(
        f"/api/tickets/{sla_tid}",
        json={"impact": "high", "urgency": "high"},
        headers=admin_headers,
    )
    assert esc_res.status_code == 200
    assert esc_res.json()["priority"] == "critical"
    admin_esc_notifs = client.get(f"/api/notifications?ticket_id={sla_tid}", headers=admin_headers).json()["items"]
    assert any(n["notification_type"] in ("high_priority_alert", "ticket_priority_updated") for n in admin_esc_notifs)

    db = TestingSessionLocal()
    try:
        sla_ticket = db.query(Ticket).filter(Ticket.id == sla_tid).first()
        assert sla_ticket is not None
        sla_ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=12)
        sla_ticket.sla_deadline = datetime.now(timezone.utc) - timedelta(minutes=15)
        db.commit()
    finally:
        db.close()

    # Trigger sync via admin notifications read twice and verify exactly one breach notification per admin
    client.get("/api/notifications", headers=admin_headers)
    first_breach_notifs = [
        n
        for n in client.get(f"/api/notifications?ticket_id={sla_tid}", headers=admin_headers).json()["items"]
        if n["notification_type"] == "sla_breached"
    ]
    assert len(first_breach_notifs) >= 1
    client.get("/api/notifications", headers=admin_headers)
    second_breach_notifs = [
        n
        for n in client.get(f"/api/notifications?ticket_id={sla_tid}", headers=admin_headers).json()["items"]
        if n["notification_type"] == "sla_breached"
    ]
    assert len(second_breach_notifs) == len(first_breach_notifs)


def test_production_smtp_unreachable_fails_fast_and_does_not_block_ticket_creation(monkeypatch):
    import errno

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(settings, "BREVO_API_KEY", "")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@nexdesk.ai")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAIL", "bb7578167@gmail.com")

    emp_headers, _, emp_email = _register_and_login("Fast Fail Employee")

    smtp_calls = {"count": 0}

    class UnreachableSMTP:
        def __init__(self, *args, **kwargs):
            smtp_calls["count"] += 1
            raise OSError(errno.ENETUNREACH, "Network is unreachable")

    with patch("app.services.notifications.email_service.smtplib.SMTP", UnreachableSMTP):
        res = client.post(
            "/api/tickets",
            json=_ticket_payload(title="Ticket during Render SMTP block"),
            headers=emp_headers,
        )
        assert res.status_code == 201
        tid = res.json()["id"]

    # Production SMTP failures fail fast with 1 attempt per email (employee + admin = 2 calls, no retries)
    assert smtp_calls["count"] == 2
    emp_notifs = client.get(f"/api/notifications?ticket_id={tid}", headers=emp_headers).json()["items"]
    assert any(n["notification_type"] == "ticket_submitted" for n in emp_notifs)

    db = TestingSessionLocal()
    try:
        logs = db.query(EmailDeliveryLog).filter(EmailDeliveryLog.ticket_id == tid).all()
        assert len(logs) >= 2
        assert all(log.delivery_status == "failed" and log.attempt_count == 1 for log in logs)
    finally:
        db.close()

    # Now verify HTTPS Email API (Resend) takes precedence over SMTP in production when configured
    admin_headers, _ = _login(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key_123")
    cfg = client.get("/api/notifications/config", headers=admin_headers).json()
    assert cfg["https_provider_configured"] is True
    assert cfg["email_transport"] == "https_api"

    mock_http_resp = MagicMock()
    mock_http_resp.status = 200
    mock_http_resp.__enter__.return_value = mock_http_resp
    mock_http_resp.__exit__.return_value = False

    with patch("app.services.notifications.email_service.urllib.request.urlopen", return_value=mock_http_resp) as mock_open:
        db = TestingSessionLocal()
        try:
            log = send_email(
                db,
                recipient_email=emp_email,
                subject="HTTPS Delivery Test",
                html_body="<p>Delivered via HTTPS</p>",
                text_body="Delivered via HTTPS",
                event_type="https_test",
                event_key=f"https_test:{tid}",
                ticket_id=tid,
            )
            assert log.delivery_status == "sent"
            assert log.attempt_count == 1
            assert mock_open.called
        finally:
            db.close()

