"""
Pydantic schemas for AI-Powered Incident Classification (Module 8).
"""
from typing import Optional
from pydantic import BaseModel, Field


class IncidentClassificationRequest(BaseModel):
    description: str = Field(
        ...,
        min_length=5,
        max_length=5000,
        description="Employee problem description in natural language",
        examples=["My company laptop suddenly stopped connecting to Wi-Fi."],
    )


class IncidentClassificationResponse(BaseModel):
    title: str = Field(..., description="Concise, professional incident title")
    category: str = Field(..., description="ITSM category (e.g. Network, Hardware, Software)")
    category_value: str = Field(..., description="Canonical category value (e.g. network)")
    subcategory: Optional[str] = Field(default=None, description="Specific subcategory (e.g. Wi-Fi)")
    impact: str = Field(..., description="Normalized impact: High, Medium, Low")
    impact_value: str = Field(..., description="Canonical impact: high, medium, low")
    urgency: str = Field(..., description="Normalized urgency: High, Medium, Low")
    urgency_value: str = Field(..., description="Canonical urgency: high, medium, low")
    recommended_priority: str = Field(..., description="Deterministic priority code (e.g. P1, P2, P3, P4)")
    priority_label: str = Field(..., description="Full priority label (e.g. P2 High)")
    priority_value: str = Field(..., description="Backend priority key (e.g. high)")
    assignment_group: str = Field(..., description="Recommended assignment group (e.g. Network Support)")
    summary: str = Field(..., description="One-sentence executive summary of the incident")
    recommended_action: str = Field(..., description="Immediate troubleshooting or triage recommendation")
    raw_llm_priority: Optional[str] = Field(
        default=None,
        description="Priority code suggested by LLM before deterministic verification",
    )
    confidence_signals: Optional[str] = Field(
        default=None,
        description="Brief explanation of extracted signals",
    )
