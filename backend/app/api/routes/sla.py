"""
SLA API routes.
Provides SLA overview, compliance tracking, and CRUD for SLA policies.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.session import get_db
from app.models.sla_policy import SLAPolicy
from app.models.user import User
from app.schemas.sla import (
    SLAOverviewResponse,
    SLAPolicyCreate,
    SLAPolicyResponse,
    SLAPolicyUpdate,
)
from app.services.analytics.service import get_sla_overview

router = APIRouter(prefix="/sla", tags=["SLA Management"])


@router.get("/overview", response_model=SLAOverviewResponse)
def get_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get full SLA overview: compliance metrics, policy stats, overdue tickets, and recent breaches."""
    return get_sla_overview(db)


@router.get("/policies", response_model=List[SLAPolicyResponse])
def list_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all SLA policies in the system."""
    policies = db.query(SLAPolicy).order_by(SLAPolicy.id.asc()).all()
    return policies


@router.post("/policies", response_model=SLAPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: SLAPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin-only: Create a new SLA policy."""
    resp_hours = payload.response_time_hours
    if resp_hours is None and payload.response_time_minutes:
        resp_hours = round(payload.response_time_minutes / 60.0, 2)

    policy = SLAPolicy(
        name=payload.name,
        priority=payload.priority.lower(),
        response_time_minutes=payload.response_time_minutes,
        response_time_hours=resp_hours or 4.0,
        resolution_time_hours=payload.resolution_time_hours,
        business_hours_only=payload.business_hours_only,
        escalation_contact=payload.escalation_contact,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.put("/policies/{policy_id}", response_model=SLAPolicyResponse)
def update_policy(
    policy_id: int,
    payload: SLAPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin-only: Update an existing SLA policy."""
    policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SLA Policy with ID {policy_id} not found",
        )

    if payload.name is not None:
        policy.name = payload.name
    if payload.response_time_minutes is not None:
        policy.response_time_minutes = payload.response_time_minutes
        policy.response_time_hours = round(payload.response_time_minutes / 60.0, 2)
    elif payload.response_time_hours is not None:
        policy.response_time_hours = payload.response_time_hours
        policy.response_time_minutes = int(payload.response_time_hours * 60)
    if payload.resolution_time_hours is not None:
        policy.resolution_time_hours = payload.resolution_time_hours
    if payload.business_hours_only is not None:
        policy.business_hours_only = payload.business_hours_only
    if payload.escalation_contact is not None:
        policy.escalation_contact = payload.escalation_contact

    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/policies/{policy_id}", status_code=status.HTTP_200_OK)
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin-only: Delete an SLA policy (fails if tickets are currently tied to it)."""
    policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SLA Policy with ID {policy_id} not found",
        )

    # Detach policy from tickets before deleting
    from app.models.ticket import Ticket
    db.query(Ticket).filter(Ticket.sla_policy_id == policy_id).update({Ticket.sla_policy_id: None})
    db.delete(policy)
    db.commit()
    return {"message": f"SLA Policy {policy_id} deleted successfully"}
