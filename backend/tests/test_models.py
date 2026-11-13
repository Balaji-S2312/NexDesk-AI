import uuid
from sqlalchemy.orm import Session
from tests.conftest import TestingSessionLocal
from app.models import (
    User,
    AssignmentGroup,
    SLAPolicy,
    Ticket,
    TicketHistory,
    Conversation,
    Message,
    Document,
    AuditLog,
)
from app.core.security import get_password_hash

def test_database_relationships_and_models():
    """
    Acceptance Criteria 7: Database relationships work across all 9 models.
    """
    db: Session = TestingSessionLocal()
    try:
        unique_suffix = uuid.uuid4().hex[:6]
        # 1. Create User
        user = User(
            name="Alice Support",
            email=f"alice_{unique_suffix}@nexdesk.ai",
            password_hash=get_password_hash("Password123!"),
            role="employee"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.id is not None

        # 2. Create Assignment Group
        group = AssignmentGroup(
            name=f"DevOps Ops {unique_suffix}",
            description="Handles server infrastructure"
        )
        db.add(group)
        db.commit()
        db.refresh(group)
        assert group.id is not None

        # 3. Create SLA Policy
        sla = SLAPolicy(
            name=f"Test SLA {unique_suffix}",
            priority="critical",
            response_time_hours=1,
            resolution_time_hours=4
        )
        db.add(sla)
        db.commit()
        db.refresh(sla)
        assert sla.id is not None

        # 4. Create Ticket
        ticket = Ticket(
            title="Database connection timeout",
            description="Postgres instance reporting high connection pool exhaustion.",
            status="open",
            priority="critical",
            category="database",
            requester_id=user.id,
            group_id=group.id,
            sla_policy_id=sla.id
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        assert ticket.id is not None

        # Verify Ticket <-> User / Group / SLA relationships
        assert ticket.requester.id == user.id
        assert ticket.group.id == group.id
        assert ticket.sla_policy.id == sla.id
        assert user.tickets_requested[0].id == ticket.id

        # 5. Create TicketHistory
        history = TicketHistory(
            ticket_id=ticket.id,
            user_id=user.id,
            field_changed="status",
            old_value="new",
            new_value="open"
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        assert history.ticket.id == ticket.id
        assert history.user.id == user.id
        assert len(ticket.histories) >= 1

        # 6. Create Conversation
        conv = Conversation(
            ticket_id=ticket.id,
            user_id=user.id
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        assert conv.ticket.id == ticket.id
        assert conv.user.id == user.id

        # 7. Create Message
        msg = Message(
            conversation_id=conv.id,
            sender_type="user",
            sender_id=user.id,
            content="We need urgent help on the database cluster."
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        assert msg.conversation.id == conv.id
        assert msg.sender.id == user.id
        assert len(conv.messages) >= 1

        # 8. Create Document
        doc = Document(
            title="Database Connection Runbook",
            content="Check max_connections and active pgbouncer pools.",
            category="database",
            created_by_id=user.id
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        assert doc.creator.id == user.id
        assert len(user.documents) >= 1

        # 9. Create AuditLog
        audit = AuditLog(
            user_id=user.id,
            action="CREATE_TICKET",
            resource_type="ticket",
            resource_id=str(ticket.id),
            details="Ticket created via API",
            ip_address="127.0.0.1"
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        assert audit.user.id == user.id
        assert len(user.audit_logs) >= 1

    finally:
        db.close()
