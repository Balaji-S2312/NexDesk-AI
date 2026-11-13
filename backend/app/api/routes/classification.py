"""
Classification API routes for AI-Powered Incident Classification (Module 8).
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.services.classifier.schemas import (
    IncidentClassificationRequest,
    IncidentClassificationResponse,
)
from app.services.classifier.service import classify_incident_description

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classification", tags=["Incident Classification"])


@router.post(
    "/classify",
    response_model=IncidentClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="AI-assisted incident classification and priority recommendation",
)
async def classify_incident_endpoint(
    payload: IncidentClassificationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    POST /api/classification/classify
    Analyzes natural language IT issue descriptions using Groq LLM signals,
    and applies deterministic backend ITIL rules to recommend:
    - Structured Title & Subcategory
    - Category & Assignment Group
    - Impact, Urgency & Deterministic Priority (P1-P4)
    - Actionable Summary & Next Steps
    """
    cleaned = payload.description.strip()
    if len(cleaned) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Description must contain at least 5 characters.",
        )

    try:
        result = await classify_incident_description(cleaned)
        return result
    except Exception as exc:
        logger.error("Failed to classify incident description: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification service error: {str(exc)}",
        )
