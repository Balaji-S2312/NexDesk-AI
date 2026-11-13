from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    # Human-readable unique ticket number, e.g. INC0000042 (set right after first flush)
    ticket_number = Column(String(20), unique=True, index=True, nullable=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="open", index=True)
    priority = Column(String(50), nullable=False, default="medium", index=True)
    category = Column(String(100), nullable=False, default="other", index=True)
    subcategory = Column(String(100), nullable=True)
    impact = Column(String(20), nullable=False, default="medium")
    urgency = Column(String(20), nullable=False, default="medium")
    response_deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    sla_deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    first_responded_at = Column(DateTime(timezone=True), nullable=True, index=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assignee_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    group_id = Column(Integer, ForeignKey("assignment_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    sla_policy_id = Column(Integer, ForeignKey("sla_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    requester = relationship("User", foreign_keys=[requester_id], back_populates="tickets_requested")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="tickets_assigned")
    group = relationship("AssignmentGroup", back_populates="tickets")
    sla_policy = relationship("SLAPolicy", back_populates="tickets")
    conversations = relationship("Conversation", back_populates="ticket", cascade="all, delete-orphan")
    histories = relationship("TicketHistory", back_populates="ticket", cascade="all, delete-orphan")
    comments = relationship("TicketComment", back_populates="ticket", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} title='{self.title[:30]}' status='{self.status}'>"


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User")

    def __repr__(self) -> str:
        return f"<TicketComment id={self.id} ticket_id={self.ticket_id} author_id={self.author_id}>"


class TicketHistory(Base):
    __tablename__ = "ticket_histories"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    field_changed = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    ticket = relationship("Ticket", back_populates="histories")
    user = relationship("User", back_populates="ticket_histories")

    def __repr__(self) -> str:
        return f"<TicketHistory id={self.id} ticket_id={self.ticket_id} field='{self.field_changed}'>"
