from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_admin
from app.database.session import get_db
from app.models.agent import AgentEscalation, AgentPendingAction, AgentToolLog
from app.models.assignment_group import AssignmentGroup
from app.models.audit_log import AuditLog
from app.models.ticket import Ticket
from app.models.user import User
from app.services.agent.schemas import (
    AdminOverrideRequest,
    AgentCancelRequest,
    AgentConfirmRequest,
    AgentConfirmResponse,
    AgentEscalateRequest,
    AgentPrepareRequest,
    EscalationOut,
    PendingActionOut,
    ToolExecutionOut,
)
from app.services.agent.tools import (
    AVAILABLE_TOOLS_SPEC,
    AgentSafetyError,
    AgentValidationError,
    DuplicateAgentActionError,
    execute_agent_tool,
    serialize_escalation,
)
from app.services.classifier.rules import normalize_category, normalize_level, resolve_assignment_group
from app.services.tickets.rules import Status
from app.services.tickets.service import TicketRuleError, as_utc, serialize_ticket, update_ticket

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agentic Workflow"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _parse_int_id(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@router.get("/tools", summary="List authorized agentic ITSM tools")
def list_agent_tools(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return {"tools": AVAILABLE_TOOLS_SPEC}


@router.post("/prepare-ticket", response_model=PendingActionOut, summary="Stage a ticket preview for user confirmation")
def prepare_ticket_endpoint(
    payload: AgentPrepareRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv_int = _parse_int_id(payload.conversation_id)
    try:
        exec_res = execute_agent_tool(
            db=db,
            user=current_user,
            tool_name="prepare_ticket",
            params={
                "description": payload.description,
                "conversation_id": conv_int,
                "attempted_troubleshooting": payload.attempted_troubleshooting or [],
            },
            conversation_id=conv_int,
            ip=_client_ip(request),
        )
        return PendingActionOut(**exec_res["result"])
    except AgentSafetyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except AgentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post(
    "/confirm",
    response_model=AgentConfirmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and route ticket strictly after explicit human confirmation",
)
def confirm_agent_ticket_endpoint(
    payload: AgentConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    overrides: Dict[str, Any] = {}
    for field in ("title", "description", "category", "subcategory", "impact", "urgency", "assignment_group"):
        val = getattr(payload, field)
        if val is not None:
            overrides[field] = val

    pending_row = (
        db.query(AgentPendingAction)
        .filter(AgentPendingAction.confirmation_id == payload.confirmation_id.strip())
        .first()
    )
    conv_id = pending_row.conversation_id if pending_row else None

    try:
        exec_res = execute_agent_tool(
            db=db,
            user=current_user,
            tool_name="create_ticket_after_confirmation",
            params={
                "confirmation_id": payload.confirmation_id,
                "overrides": overrides,
                "escalate": payload.escalate_to_human,
                "ip": _client_ip(request),
            },
            conversation_id=conv_id,
            ip=_client_ip(request),
        )
        data = exec_res["result"]
        tool_out = ToolExecutionOut(
            tool_name=exec_res["tool_name"],
            status=exec_res["status"],
            summary=exec_res["summary"],
            execution_ms=exec_res["execution_ms"],
            data={"ticket_number": data["ticket"]["ticket_number"]},
        )
        return AgentConfirmResponse(
            confirmation_id=data["confirmation_id"],
            status=data["status"],
            ticket=data["ticket"],
            escalation=data.get("escalation"),
            tool_calls=[tool_out],
            message=f"Ticket {data['ticket']['ticket_number']} created and routed to {data['ticket'].get('assigned_group') or 'support team'}.",
        )
    except DuplicateAgentActionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except AgentSafetyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except AgentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post("/cancel", summary="Cancel a pending Human-in-the-Loop confirmation request")
def cancel_agent_ticket_endpoint(
    payload: AgentCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    pending = (
        db.query(AgentPendingAction)
        .filter(AgentPendingAction.confirmation_id == payload.confirmation_id.strip())
        .first()
    )
    if not pending:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending action not found.")
    if pending.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to cancel this action.")
    if pending.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Action has already been confirmed and cannot be cancelled.",
        )

    pending.status = "cancelled"
    pending.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"confirmation_id": pending.confirmation_id, "status": "cancelled"}


@router.post(
    "/escalate",
    response_model=EscalationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a human escalation handoff record and optionally route an existing ticket",
)
def escalate_to_human_endpoint(
    payload: AgentEscalateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv_int = _parse_int_id(payload.conversation_id)
    try:
        exec_res = execute_agent_tool(
            db=db,
            user=current_user,
            tool_name="escalate_to_human",
            params={
                "reason": payload.reason,
                "conversation_id": conv_int,
                "ticket_id": payload.ticket_id,
                "attempted_troubleshooting": payload.attempted_troubleshooting,
                "recommended_group": payload.recommended_group,
                "ip": _client_ip(request),
            },
            conversation_id=conv_int,
            ip=_client_ip(request),
        )
        return EscalationOut(**exec_res["result"])
    except AgentSafetyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except AgentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/escalations", response_model=List[EscalationOut], summary="List human escalation records")
def list_escalations_endpoint(
    ticket_id: Optional[int] = Query(None),
    conversation_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AgentEscalation).options(
        joinedload(AgentEscalation.ticket),
        joinedload(AgentEscalation.user),
    )
    if current_user.role != "admin":
        query = query.filter(AgentEscalation.user_id == current_user.id)
    if ticket_id is not None:
        query = query.filter(AgentEscalation.ticket_id == ticket_id)
    if conversation_id is not None:
        query = query.filter(AgentEscalation.conversation_id == conversation_id)

    rows = query.order_by(AgentEscalation.created_at.desc()).limit(50).all()
    return [EscalationOut(**serialize_escalation(r)) for r in rows]


@router.post(
    "/tickets/{ticket_id}/override",
    summary="Administrator override for AI ticket recommendations",
)
def admin_override_ai_recommendations(
    ticket_id: int,
    payload: AdminOverrideRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.requester), joinedload(Ticket.group))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    changes: Dict[str, Any] = {}
    if payload.category is not None:
        changes["category"] = normalize_category(payload.category)
    if payload.subcategory is not None:
        changes["subcategory"] = payload.subcategory.strip() or None
    if payload.impact is not None:
        changes["impact"] = normalize_level(payload.impact, default=ticket.impact)
    if payload.urgency is not None:
        changes["urgency"] = normalize_level(payload.urgency, default=ticket.urgency)
    if payload.status is not None:
        try:
            changes["status"] = Status(payload.status.strip().lower()).value
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid ticket status.")

    if payload.group_id is not None:
        changes["group_id"] = payload.group_id
    elif payload.assignment_group is not None:
        resolved_name = resolve_assignment_group(changes.get("category", ticket.category), payload.assignment_group)
        grp = db.query(AssignmentGroup).filter(AssignmentGroup.name.ilike(resolved_name)).first()
        if not grp:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Assignment group '{payload.assignment_group}' not found.",
            )
        changes["group_id"] = grp.id

    try:
        recorded = update_ticket(db, ticket, admin_user, changes, ip=_client_ip(request))
    except TicketRuleError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    db.add(
        AuditLog(
            user_id=admin_user.id,
            action="ADMIN_OVERRIDE_AI_RECOMMENDATION",
            resource_type="ticket",
            resource_id=str(ticket.id),
            details=f"{ticket.ticket_number}: {payload.override_reason.strip()}",
            ip_address=_client_ip(request),
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    refreshed = (
        db.query(Ticket)
        .options(joinedload(Ticket.requester), joinedload(Ticket.group))
        .filter(Ticket.id == ticket.id)
        .first()
    )
    return {
        "ticket": serialize_ticket(refreshed or ticket),
        "override_reason": payload.override_reason.strip(),
        "changes_count": len(recorded),
    }


@router.get("/logs", summary="Inspect recorded agentic tool executions")
def list_agent_tool_logs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    q = db.query(AgentToolLog)
    if current_user.role != "admin":
        q = q.filter(AgentToolLog.user_id == current_user.id)
    rows = q.order_by(AgentToolLog.created_at.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": r.id,
                "conversation_id": r.conversation_id,
                "user_id": r.user_id,
                "tool_name": r.tool_name,
                "status": r.status,
                "input_summary": r.input_summary,
                "output_summary": r.output_summary,
                "execution_ms": r.execution_ms,
                "created_at": as_utc(r.created_at),
            }
            for r in rows
        ],
        "total": len(rows),
    }
