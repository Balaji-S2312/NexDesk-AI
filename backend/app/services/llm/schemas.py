from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

from app.services.agent.schemas import PendingActionOut, ToolExecutionOut


class ActionItem(BaseModel):
    action_type: str = Field(
        ...,
        description="e.g., 'create_ticket', 'suggested_step', 'follow_up', 'escalate'",
    )
    label: str = Field(..., description="Action button label")
    payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Suggested payload, e.g., title, description, category, priority",
    )


class SourceReference(BaseModel):
    id: Optional[str] = None
    document_id: Optional[int] = None
    filename: Optional[str] = None
    title: str
    page_number: Optional[int] = None
    score: Optional[float] = None
    category: Optional[str] = None
    snippet: Optional[str] = None


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(
        default=None, description="ID of existing conversation, or null for new"
    )
    message: str = Field(..., min_length=1, max_length=5000, description="User's query")


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    sources: List[SourceReference] = Field(default_factory=list)
    actions: List[ActionItem] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    rag_used: bool = False
    retrieved_chunks_count: int = 0
    tool_calls: List[ToolExecutionOut] = Field(default_factory=list)
    pending_action: Optional[PendingActionOut] = None


class LLMStructuredOutput(BaseModel):
    answer: str = Field(..., description="Troubleshooting guide or answer to user")
    suggested_actions: List[ActionItem] = Field(default_factory=list)
    incident_draft: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Pre-filled draft ticket details if an incident is detected",
    )
