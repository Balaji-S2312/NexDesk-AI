from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.session import Base


class AgentPendingAction(Base):
    __tablename__ = "agent_pending_actions"

    id = Column(Integer, primary_key=True, index=True)
    confirmation_id = Column(String(64), unique=True, nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False, default="create_ticket")
    status = Column(String(50), nullable=False, default="pending_confirmation", index=True)
    payload_json = Column(Text, nullable=False)
    result_ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True, index=True)
    result_escalation_id = Column(Integer, nullable=True)
    confirmed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    confirmed_by = relationship("User", foreign_keys=[confirmed_by_id])
    conversation = relationship("Conversation")
    ticket = relationship("Ticket")


class AgentToolLog(Base):
    __tablename__ = "agent_tool_logs"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tool_name = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    execution_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    user = relationship("User")
    conversation = relationship("Conversation")


class AgentEscalation(Base):
    __tablename__ = "agent_escalations"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recommended_group_id = Column(Integer, ForeignKey("assignment_groups.id", ondelete="SET NULL"), nullable=True)
    recommended_group_name = Column(String(100), nullable=False)
    escalation_summary = Column(Text, nullable=False)
    attempted_troubleshooting = Column(Text, nullable=True)
    relevant_conversation = Column(Text, nullable=True)
    retrieved_references = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="routed", index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    ticket = relationship("Ticket")
    conversation = relationship("Conversation")
    user = relationship("User")
    recommended_group = relationship("AssignmentGroup")
