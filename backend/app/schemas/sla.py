"""
Pydantic schemas for SLA policy management and SLA overview.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SLAPolicyBase(BaseModel):
    name: str = Field(..., max_length=100)
    priority: str = Field(..., description="critical, high, medium, low")
    response_time_minutes: int = Field(..., ge=1, description="Target response time in minutes")
    response_time_hours: Optional[float] = Field(None, description="Target response time in hours")
    resolution_time_hours: int = Field(..., ge=1, description="Target resolution time in hours")
    business_hours_only: bool = Field(False, description="Whether SLA applies to 9-5 business hours only")
    escalation_contact: Optional[str] = Field(None, max_length=255)


class SLAPolicyCreate(SLAPolicyBase):
    pass


class SLAPolicyUpdate(BaseModel):
    name: Optional[str] = None
    response_time_minutes: Optional[int] = None
    response_time_hours: Optional[float] = None
    resolution_time_hours: Optional[int] = None
    business_hours_only: Optional[bool] = None
    escalation_contact: Optional[str] = None


class SLAPolicyResponse(SLAPolicyBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SLAPolicyMetrics(BaseModel):
    policy: SLAPolicyResponse
    active_tickets: int = 0
    resolved_tickets: int = 0
    breached_tickets: int = 0
    compliance_rate: float = 100.0


class SLAIncidentItem(BaseModel):
    id: int
    ticket_number: str
    title: str
    priority: str
    priority_label: str
    status: str
    assigned_group: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    response_deadline: Optional[datetime] = None
    resolution_deadline: Optional[datetime] = None
    first_responded_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    response_breached: bool = False
    resolution_breached: bool = False
    is_overdue: bool = False
    is_near_breach: bool = False
    sla_status: str
    ticket_age_display: str


class SLAOverviewResponse(BaseModel):
    total_evaluated: int
    total_breached: int
    total_overdue: int
    overall_compliance_rate: float
    response_compliance_rate: float
    resolution_compliance_rate: float
    policies: List[SLAPolicyMetrics]
    overdue_incidents: List[SLAIncidentItem]
    recent_breaches: List[SLAIncidentItem]
