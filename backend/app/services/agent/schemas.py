from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolExecutionOut(BaseModel):
    tool_name: str
    status: str
    summary: str
    execution_ms: int = 0
    data: Optional[Dict[str, Any]] = None


class PendingActionOut(BaseModel):
    confirmation_id: str
    action_type: str
    status: str
    conversation_id: Optional[str] = None
    title: str
    description: str
    category: str
    category_value: str
    subcategory: Optional[str] = None
    impact: str
    impact_value: str
    urgency: str
    urgency_value: str
    recommended_priority: str
    priority_label: str
    assignment_group: str
    group_id: Optional[int] = None
    summary: str
    recommended_action: str
    attempted_troubleshooting: List[str] = Field(default_factory=list)
    retrieved_sources: List[Dict[str, Any]] = Field(default_factory=list)
    escalation_summary: Optional[str] = None
    created_ticket_id: Optional[int] = None
    created_ticket_number: Optional[str] = None


class AgentConfirmRequest(BaseModel):
    confirmation_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    impact: Optional[str] = None
    urgency: Optional[str] = None
    assignment_group: Optional[str] = None
    escalate_to_human: bool = True


class AgentConfirmResponse(BaseModel):
    confirmation_id: str
    status: str
    ticket: Dict[str, Any]
    escalation: Optional[Dict[str, Any]] = None
    tool_calls: List[ToolExecutionOut] = Field(default_factory=list)
    message: str


class AgentCancelRequest(BaseModel):
    confirmation_id: str


class AgentPrepareRequest(BaseModel):
    description: str = Field(..., min_length=5, max_length=5000)
    conversation_id: Optional[str] = None
    attempted_troubleshooting: Optional[List[str]] = None


class AgentEscalateRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=5000)
    conversation_id: Optional[str] = None
    ticket_id: Optional[int] = None
    attempted_troubleshooting: Optional[List[str]] = None
    recommended_group: Optional[str] = None


class AdminOverrideRequest(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    impact: Optional[str] = None
    urgency: Optional[str] = None
    group_id: Optional[int] = None
    assignment_group: Optional[str] = None
    status: Optional[str] = None
    override_reason: str = Field(..., min_length=3, max_length=1000)


class EscalationOut(BaseModel):
    id: int
    ticket_id: Optional[int] = None
    ticket_number: Optional[str] = None
    conversation_id: Optional[int] = None
    user_id: int
    user_name: Optional[str] = None
    recommended_group_id: Optional[int] = None
    recommended_group_name: str
    escalation_summary: str
    attempted_troubleshooting: List[str] = Field(default_factory=list)
    relevant_conversation: Optional[str] = None
    retrieved_references: List[Dict[str, Any]] = Field(default_factory=list)
    status: str
    created_at: datetime
