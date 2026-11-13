from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.tickets.rules import Category, Impact, Status, Urgency


def _clean(v: Optional[str]) -> Optional[str]:
    return v.strip() if isinstance(v, str) else v


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10, max_length=10000)
    category: Category
    subcategory: Optional[str] = Field(default=None, max_length=100)
    impact: Impact
    urgency: Urgency

    @field_validator("title", "description", "subcategory")
    @classmethod
    def strip_text(cls, v):
        return _clean(v)

    @field_validator("title", "description")
    @classmethod
    def not_blank_after_strip(cls, v):
        if not v or len(v) < 5:
            raise ValueError("must not be blank")
        return v


class TicketUpdate(BaseModel):
    """All fields optional (PATCH). Priority is derived and cannot be set directly."""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=5, max_length=255)
    description: Optional[str] = Field(default=None, min_length=10, max_length=10000)
    category: Optional[Category] = None
    subcategory: Optional[str] = Field(default=None, max_length=100)
    impact: Optional[Impact] = None
    urgency: Optional[Urgency] = None
    status: Optional[Status] = None
    group_id: Optional[int] = None
    resolution_notes: Optional[str] = Field(default=None, max_length=10000)

    @field_validator("title", "description", "subcategory", "resolution_notes")
    @classmethod
    def strip_text(cls, v):
        return _clean(v)


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    title: str
    description: str
    category: str
    subcategory: Optional[str] = None
    impact: str
    urgency: str
    priority: str
    priority_label: str
    status: str
    group_id: Optional[int] = None
    assigned_group: Optional[str] = None
    requester_id: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    response_deadline: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None
    first_responded_at: Optional[datetime] = None
    sla_breached: bool
    response_breached: bool = False
    resolution_breached: bool = False
    is_overdue: bool = False
    is_near_breach: bool = False
    sla_status: Optional[str] = None
    ticket_age_hours: Optional[float] = None
    ticket_age_display: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None


class TicketListOut(BaseModel):
    items: List[TicketOut]
    total: int
    page: int
    page_size: int


class TicketHistoryOut(BaseModel):
    id: int
    ticket_id: int
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: Optional[str] = None
    changed_by_id: Optional[int] = None
    created_at: datetime


class AssignmentGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None


class TicketCommentCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)

    @field_validator("message")
    @classmethod
    def clean_non_blank(cls, v: str) -> str:
        cleaned = (v or "").strip()
        if not cleaned:
            raise ValueError("Comment message cannot be blank")
        return cleaned


class TicketCommentOut(BaseModel):
    id: int
    ticket_id: int
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    author_role: Optional[str] = None
    message: str
    created_at: datetime
