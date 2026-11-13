import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.agent import AgentEscalation, AgentPendingAction, AgentToolLog
from app.models.assignment_group import AssignmentGroup
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation, Message
from app.models.ticket import Ticket, TicketHistory
from app.models.user import User
from app.services.classifier.rules import (
    CATEGORY_DISPLAY_LABELS,
    evaluate_priority_matrix,
    normalize_category,
    normalize_level,
    resolve_assignment_group,
)
from app.services.classifier.service import (
    _heuristic_classification,
    classify_incident_description,
)
from app.services.rag.retriever import retrieve_relevant_context
from app.services.tickets.rules import DEFAULT_RESOLUTION_HOURS
from app.services.tickets.service import as_utc, create_ticket, serialize_ticket

logger = logging.getLogger(__name__)


class AgentSafetyError(ValueError):
    """Raised when a tool call violates human-in-the-loop, RBAC, or safety guardrails."""


class AgentValidationError(ValueError):
    """Raised when required tool parameters or state prerequisites fail validation."""


class DuplicateAgentActionError(ValueError):
    """Raised when a confirmed pending action is submitted again."""


FORBIDDEN_AUTO_TOOLS = {
    "close_ticket",
    "auto_close_ticket",
    "delete_ticket",
    "force_create_ticket",
}

AVAILABLE_TOOLS_SPEC: List[Dict[str, Any]] = [
    {
        "name": "search_knowledge_base",
        "description": "Search indexed ChromaDB IT documentation using semantic similarity.",
        "requires_confirmation": False,
        "allowed_roles": ["employee", "admin"],
    },
    {
        "name": "classify_incident",
        "description": "Extract structured ITSM category, impact, urgency, and summary signals.",
        "requires_confirmation": False,
        "allowed_roles": ["employee", "admin"],
    },
    {
        "name": "recommend_priority",
        "description": "Deterministically compute ITIL priority and SLA target from impact and urgency.",
        "requires_confirmation": False,
        "allowed_roles": ["employee", "admin"],
    },
    {
        "name": "recommend_assignment_group",
        "description": "Recommend and resolve the target human support group from category.",
        "requires_confirmation": False,
        "allowed_roles": ["employee", "admin"],
    },
    {
        "name": "get_ticket_status",
        "description": "Retrieve live status and SLA details for authorized tickets.",
        "requires_confirmation": False,
        "allowed_roles": ["employee", "admin"],
    },
    {
        "name": "prepare_ticket",
        "description": "Stage a structured ticket preview awaiting explicit user confirmation.",
        "requires_confirmation": False,
        "allowed_roles": ["employee", "admin"],
    },
    {
        "name": "create_ticket_after_confirmation",
        "description": "Create and route an IT ticket strictly after explicit human confirmation.",
        "requires_confirmation": True,
        "allowed_roles": ["employee", "admin"],
    },
    {
        "name": "escalate_to_human",
        "description": "Build and route an escalation handoff record with conversation and troubleshooting history.",
        "requires_confirmation": False,
        "allowed_roles": ["employee", "admin"],
    },
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_dumps_safe(data: Any) -> str:
    return json.dumps(data, default=str)


def _safe_loads_list(raw: Optional[str]) -> List[Any]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _format_conversation_excerpt(db: Session, conversation_id: Optional[int], limit: int = 10) -> str:
    if not conversation_id:
        return ""
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    tail = msgs[-limit:]
    lines = []
    for m in tail:
        speaker = "Employee" if m.sender_type == "user" else ("System" if m.sender_type == "system" else "NexDesk AI")
        snippet = " ".join((m.content or "").split())[:280]
        lines.append(f"{speaker}: {snippet}")
    return "\n".join(lines)


def _extract_troubleshooting_from_db(db: Session, conversation_id: Optional[int]) -> List[str]:
    if not conversation_id:
        return []
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.sender_type == "agent")
        .order_by(Message.created_at.asc())
        .all()
    )
    steps: List[str] = []
    for m in msgs:
        for line in (m.content or "").splitlines():
            clean = line.strip()
            if re.match(r"^(\d+[\.\)]|[-*])\s+", clean):
                step_text = re.sub(r"^(\d+[\.\)]|[-*])\s+", "", clean).strip()
                if len(step_text) >= 8 and step_text not in steps:
                    steps.append(step_text[:180])
    return steps[:6]


def serialize_escalation(esc: AgentEscalation) -> Dict[str, Any]:
    return {
        "id": esc.id,
        "ticket_id": esc.ticket_id,
        "ticket_number": esc.ticket.ticket_number if esc.ticket else None,
        "conversation_id": esc.conversation_id,
        "user_id": esc.user_id,
        "user_name": esc.user.name if esc.user else None,
        "recommended_group_id": esc.recommended_group_id,
        "recommended_group_name": esc.recommended_group_name,
        "escalation_summary": esc.escalation_summary,
        "attempted_troubleshooting": _safe_loads_list(esc.attempted_troubleshooting),
        "relevant_conversation": esc.relevant_conversation,
        "retrieved_references": _safe_loads_list(esc.retrieved_references),
        "status": esc.status,
        "created_at": as_utc(esc.created_at),
    }


def _pending_to_dict(pending: AgentPendingAction, ticket: Optional[Ticket] = None) -> Dict[str, Any]:
    payload = json.loads(pending.payload_json)
    return {
        "confirmation_id": pending.confirmation_id,
        "action_type": pending.action_type,
        "status": pending.status,
        "conversation_id": str(pending.conversation_id) if pending.conversation_id is not None else None,
        "title": payload["title"],
        "description": payload["description"],
        "category": payload["category"],
        "category_value": payload["category_value"],
        "subcategory": payload.get("subcategory"),
        "impact": payload["impact"],
        "impact_value": payload["impact_value"],
        "urgency": payload["urgency"],
        "urgency_value": payload["urgency_value"],
        "recommended_priority": payload["recommended_priority"],
        "priority_label": payload["priority_label"],
        "assignment_group": payload["assignment_group"],
        "group_id": payload.get("group_id"),
        "summary": payload["summary"],
        "recommended_action": payload["recommended_action"],
        "attempted_troubleshooting": payload.get("attempted_troubleshooting", []),
        "retrieved_sources": payload.get("retrieved_sources", []),
        "escalation_summary": payload.get("escalation_summary"),
        "created_ticket_id": pending.result_ticket_id,
        "created_ticket_number": ticket.ticket_number if ticket else payload.get("created_ticket_number"),
    }


# ---------------------------------------------------------------------------
# Tool 1: search_knowledge_base
# ---------------------------------------------------------------------------
def tool_search_knowledge_base(
    db: Session,
    user: User,
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    cleaned = (query or "").strip()
    if len(cleaned) < 2:
        raise AgentValidationError("Knowledge base query must not be empty.")
    res = retrieve_relevant_context(cleaned, top_k=top_k, category=category)
    chunks_out = [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "filename": c.source_filename,
            "title": c.title,
            "category": c.category,
            "page_number": c.page_number,
            "score": round(c.score, 4),
            "snippet": " ".join(c.text.split())[:240],
        }
        for c in res.chunks
    ]
    return {
        "query": cleaned,
        "rag_used": res.has_relevant_docs,
        "retained_count": res.retained_count,
        "chunks": chunks_out,
        "context_text": res.context_text,
        "retrieval_result": res,
    }


# ---------------------------------------------------------------------------
# Tool 2: classify_incident
# ---------------------------------------------------------------------------
def tool_classify_incident(
    db: Session,
    user: User,
    description: str,
) -> Dict[str, Any]:
    cleaned = (description or "").strip()
    if len(cleaned) < 5:
        raise AgentValidationError("Incident description must be at least 5 characters.")

    raw = _heuristic_classification(cleaned)
    cat_val = normalize_category(str(raw.get("category", "")))
    cat_display = CATEGORY_DISPLAY_LABELS.get(cat_val, "Other")
    subcat = str(raw.get("subcategory") or "").strip() or None
    impact_val = normalize_level(str(raw.get("impact", "")), default="medium")
    urgency_val = normalize_level(str(raw.get("urgency", "")), default="medium")
    priority_key, priority_code, priority_label = evaluate_priority_matrix(impact_val, urgency_val)
    assignment_group = resolve_assignment_group(cat_val, raw.get("assignment_group"))

    title = str(raw.get("title") or "").strip()
    if len(title) < 5:
        title = f"{cat_display} Support Issue"

    return {
        "title": title[:120],
        "category": cat_display,
        "category_value": cat_val,
        "subcategory": subcat,
        "impact": impact_val.capitalize(),
        "impact_value": impact_val,
        "urgency": urgency_val.capitalize(),
        "urgency_value": urgency_val,
        "recommended_priority": priority_code,
        "priority_label": priority_label,
        "priority_value": priority_key,
        "assignment_group": assignment_group,
        "summary": str(raw.get("summary") or f"Employee reported a {cat_display.lower()} issue."),
        "recommended_action": str(raw.get("recommended_action") or f"Route to {assignment_group}."),
    }


async def tool_classify_incident_async(
    db: Session,
    user: User,
    description: str,
) -> Dict[str, Any]:
    cleaned = (description or "").strip()
    if len(cleaned) < 5:
        raise AgentValidationError("Incident description must be at least 5 characters.")
    res = await classify_incident_description(cleaned)
    return res.model_dump()


# ---------------------------------------------------------------------------
# Tool 3: recommend_priority
# ---------------------------------------------------------------------------
def tool_recommend_priority(
    db: Session,
    user: User,
    impact: str,
    urgency: str,
) -> Dict[str, Any]:
    norm_impact = normalize_level(impact, default="")
    norm_urgency = normalize_level(urgency, default="")
    if norm_impact not in {"high", "medium", "low"} or norm_urgency not in {"high", "medium", "low"}:
        raise AgentValidationError("Impact and urgency must be high, medium, or low.")
    p_key, p_code, p_label = evaluate_priority_matrix(norm_impact, norm_urgency)
    return {
        "impact": norm_impact.capitalize(),
        "impact_value": norm_impact,
        "urgency": norm_urgency.capitalize(),
        "urgency_value": norm_urgency,
        "priority_value": p_key,
        "recommended_priority": p_code,
        "priority_label": p_label,
        "sla_resolution_hours": DEFAULT_RESOLUTION_HOURS[p_key],
    }


# ---------------------------------------------------------------------------
# Tool 4: recommend_assignment_group
# ---------------------------------------------------------------------------
def tool_recommend_assignment_group(
    db: Session,
    user: User,
    category: str,
    preferred_group: Optional[str] = None,
) -> Dict[str, Any]:
    cat_val = normalize_category(category)
    group_name = resolve_assignment_group(cat_val, preferred_group)
    group = (
        db.query(AssignmentGroup)
        .filter(AssignmentGroup.name.ilike(group_name))
        .first()
    )
    if not group:
        group = AssignmentGroup(
            name=group_name,
            description=f"ITSM escalation queue for {CATEGORY_DISPLAY_LABELS.get(cat_val, 'General')} issues.",
        )
        db.add(group)
        db.flush()
    return {
        "category": cat_val,
        "assignment_group": group.name,
        "group_id": group.id,
        "description": group.description or "",
    }


# ---------------------------------------------------------------------------
# Tool 5: get_ticket_status
# ---------------------------------------------------------------------------
def tool_get_ticket_status(
    db: Session,
    user: User,
    ticket_reference: Optional[str] = None,
) -> Dict[str, Any]:
    if ticket_reference and ticket_reference.strip():
        ref = ticket_reference.strip().upper().lstrip("#")
        query = db.query(Ticket).options(joinedload(Ticket.requester), joinedload(Ticket.group))
        ticket = None
        if ref.startswith("INC"):
            ticket = query.filter(Ticket.ticket_number == ref).first()
        elif ref.isdigit():
            ticket = query.filter(Ticket.id == int(ref)).first()
        else:
            ticket = query.filter(Ticket.ticket_number.ilike(f"%{ref}%")).first()

        if not ticket or (user.role != "admin" and ticket.requester_id != user.id):
            raise AgentSafetyError("Requested ticket was not found or you do not have permission to view it.")
        return {"tickets": [serialize_ticket(ticket)], "count": 1}

    q = db.query(Ticket).options(joinedload(Ticket.requester), joinedload(Ticket.group))
    if user.role != "admin":
        q = q.filter(Ticket.requester_id == user.id)
    rows = q.order_by(Ticket.updated_at.desc()).limit(3).all()
    return {"tickets": [serialize_ticket(t) for t in rows], "count": len(rows)}


# ---------------------------------------------------------------------------
# Tool 6: prepare_ticket
# ---------------------------------------------------------------------------
def tool_prepare_ticket(
    db: Session,
    user: User,
    description: str,
    conversation_id: Optional[int] = None,
    title: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    impact: Optional[str] = None,
    urgency: Optional[str] = None,
    attempted_troubleshooting: Optional[List[str]] = None,
    retrieved_sources: Optional[List[Dict[str, Any]]] = None,
    escalation_summary: Optional[str] = None,
) -> Dict[str, Any]:
    cleaned_desc = (description or "").strip()
    if len(cleaned_desc) < 5:
        raise AgentValidationError("Problem description is required to prepare a ticket.")

    classified = tool_classify_incident(db, user, cleaned_desc)

    cat_val = normalize_category(category) if category else classified["category_value"]
    cat_display = CATEGORY_DISPLAY_LABELS.get(cat_val, classified["category"])
    subcat = (subcategory or "").strip() or classified.get("subcategory")
    impact_val = normalize_level(impact, default=classified["impact_value"]) if impact else classified["impact_value"]
    urgency_val = normalize_level(urgency, default=classified["urgency_value"]) if urgency else classified["urgency_value"]

    prio = tool_recommend_priority(db, user, impact_val, urgency_val)
    grp = tool_recommend_assignment_group(db, user, cat_val)

    final_title = (title or classified["title"]).strip()
    if len(final_title) < 5:
        final_title = f"{cat_display} Incident Escalation"

    steps = [s for s in (attempted_troubleshooting or []) if s and s.strip()]
    if not steps and conversation_id:
        steps = _extract_troubleshooting_from_db(db, conversation_id)

    sources = retrieved_sources or []
    summary_text = escalation_summary or classified["summary"]

    enriched_desc_parts = [cleaned_desc]
    if steps:
        enriched_desc_parts.append(
            "Attempted Troubleshooting:\n" + "\n".join(f"- {s}" for s in steps)
        )
    if sources:
        refs = ", ".join(
            f"{s.get('filename') or s.get('title')} (p.{s.get('page_number', 1)})" for s in sources[:3]
        )
        enriched_desc_parts.append(f"Referenced Knowledge Base Docs: {refs}")
    final_description = "\n\n".join(enriched_desc_parts)
    if len(final_description) < 10:
        final_description = f"{final_description} - Employee requests IT assistance."

    payload_dict: Dict[str, Any] = {
        "title": final_title[:255],
        "description": final_description[:10000],
        "category": cat_display,
        "category_value": cat_val,
        "subcategory": subcat,
        "impact": prio["impact"],
        "impact_value": prio["impact_value"],
        "urgency": prio["urgency"],
        "urgency_value": prio["urgency_value"],
        "recommended_priority": prio["recommended_priority"],
        "priority_label": prio["priority_label"],
        "assignment_group": grp["assignment_group"],
        "group_id": grp["group_id"],
        "summary": summary_text,
        "recommended_action": classified["recommended_action"],
        "attempted_troubleshooting": steps,
        "retrieved_sources": sources,
        "escalation_summary": summary_text,
    }

    idem_source = f"{user.id}:{conversation_id or 0}:{cat_val}:{final_title.lower()}"
    idem_key = hashlib.sha256(idem_source.encode("utf-8")).hexdigest()

    existing = None
    if conversation_id is not None:
        existing = (
            db.query(AgentPendingAction)
            .filter(
                AgentPendingAction.user_id == user.id,
                AgentPendingAction.conversation_id == conversation_id,
                AgentPendingAction.status == "pending_confirmation",
            )
            .first()
        )
    else:
        existing = (
            db.query(AgentPendingAction)
            .filter(
                AgentPendingAction.user_id == user.id,
                AgentPendingAction.idempotency_key == idem_key,
                AgentPendingAction.status == "pending_confirmation",
            )
            .first()
        )

    now = _utc_now()
    if existing:
        existing.payload_json = _json_dumps_safe(payload_dict)
        existing.updated_at = now
        existing.action_type = "create_and_escalate" if steps else "create_ticket"
        pending = existing
    else:
        pending = AgentPendingAction(
            confirmation_id=str(uuid.uuid4()),
            idempotency_key=idem_key,
            conversation_id=conversation_id,
            user_id=user.id,
            action_type="create_and_escalate" if steps else "create_ticket",
            status="pending_confirmation",
            payload_json=_json_dumps_safe(payload_dict),
            created_at=now,
            updated_at=now,
        )
        db.add(pending)

    db.commit()
    db.refresh(pending)
    return _pending_to_dict(pending)


# ---------------------------------------------------------------------------
# Tool 7: create_ticket_after_confirmation
# ---------------------------------------------------------------------------
def tool_create_ticket_after_confirmation(
    db: Session,
    user: User,
    confirmation_id: str,
    overrides: Optional[Dict[str, Any]] = None,
    escalate: bool = True,
    ip: Optional[str] = None,
) -> Dict[str, Any]:
    if not confirmation_id or not confirmation_id.strip():
        raise AgentValidationError("A valid confirmation_id is required before creating a ticket.")

    pending = (
        db.query(AgentPendingAction)
        .filter(AgentPendingAction.confirmation_id == confirmation_id.strip())
        .first()
    )
    if not pending:
        raise AgentValidationError("Confirmation request was not found.")

    if pending.user_id != user.id and user.role != "admin":
        raise AgentSafetyError("You are not authorized to confirm another user's pending ticket.")

    target_user = db.query(User).filter(User.id == pending.user_id).first() or user
    if getattr(target_user, "role", None) == "employee" and not getattr(target_user, "email_verified", False):
        raise AgentSafetyError("Email verification required. Please verify your employee email address before creating IT support tickets.")

    if pending.status == "confirmed":
        raise DuplicateAgentActionError(
            f"Confirmation {confirmation_id} has already been processed (Ticket ID {pending.result_ticket_id})."
        )
    if pending.status == "cancelled":
        raise AgentValidationError("Cannot confirm an action that has already been cancelled.")

    payload = json.loads(pending.payload_json)
    overrides = overrides or {}

    final_title = (overrides.get("title") or payload["title"]).strip()
    if len(final_title) < 5:
        raise AgentValidationError("Ticket title must be at least 5 characters.")

    final_description = (overrides.get("description") or payload["description"]).strip()
    if len(final_description) < 10:
        raise AgentValidationError("Ticket description must be at least 10 characters.")

    raw_cat = overrides.get("category") or payload["category_value"]
    final_category = normalize_category(raw_cat)
    final_subcategory = (
        overrides.get("subcategory")
        if overrides.get("subcategory") is not None
        else payload.get("subcategory")
    )
    final_impact = normalize_level(overrides.get("impact") or payload["impact_value"], default="medium")
    final_urgency = normalize_level(overrides.get("urgency") or payload["urgency_value"], default="medium")

    # Resolve target requester (if admin confirms on behalf of requester, requester remains owner)
    requester = db.query(User).filter(User.id == pending.user_id).first() or user

    ticket = create_ticket(
        db=db,
        requester=requester,
        data={
            "title": final_title[:255],
            "description": final_description[:10000],
            "category": final_category,
            "subcategory": final_subcategory,
            "impact": final_impact,
            "urgency": final_urgency,
        },
        ip=ip,
    )

    # Resolve and assign target group automatically
    group_info = tool_recommend_assignment_group(
        db,
        user,
        category=final_category,
        preferred_group=overrides.get("assignment_group") or payload.get("assignment_group"),
    )
    now = _utc_now()
    if group_info.get("group_id"):
        old_status = ticket.status
        ticket.group_id = group_info["group_id"]
        ticket.status = "assigned"
        ticket.updated_at = now
        db.add(
            TicketHistory(
                ticket_id=ticket.id,
                user_id=user.id,
                field_changed="assigned_group",
                old_value=None,
                new_value=group_info["assignment_group"],
                created_at=now,
            )
        )
        db.add(
            TicketHistory(
                ticket_id=ticket.id,
                user_id=user.id,
                field_changed="status",
                old_value=old_status,
                new_value="assigned",
                created_at=now,
            )
        )

    if pending.conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == pending.conversation_id).first()
        if conv and not conv.ticket_id:
            conv.ticket_id = ticket.id
            conv.updated_at = now

    escalation_dict: Optional[Dict[str, Any]] = None
    should_escalate = escalate or pending.action_type == "create_and_escalate"
    if should_escalate:
        esc = _create_escalation_record(
            db=db,
            user=requester,
            ticket=ticket,
            conversation_id=pending.conversation_id,
            group_id=group_info.get("group_id"),
            group_name=group_info["assignment_group"],
            summary=payload.get("escalation_summary") or payload.get("summary") or final_title,
            attempted_steps=payload.get("attempted_troubleshooting", []),
            retrieved_sources=payload.get("retrieved_sources", []),
            ip=ip,
        )
        pending.result_escalation_id = esc.id
        escalation_dict = serialize_escalation(esc)

    pending.status = "confirmed"
    pending.result_ticket_id = ticket.id
    pending.confirmed_by_id = user.id
    pending.confirmed_at = now
    pending.updated_at = now

    if pending.conversation_id:
        db.add(
            Message(
                conversation_id=pending.conversation_id,
                sender_type="system",
                sender_id=None,
                content=(
                    f"Confirmed by user: created {ticket.ticket_number} "
                    f"[{ticket.priority.upper()}] routed to {group_info['assignment_group']}."
                ),
                created_at=now,
            )
        )

    db.commit()
    db.refresh(ticket)
    if group_info.get("group_id"):
        try:
            from app.services.notifications.notification_service import notify_ticket_assigned

            notify_ticket_assigned(
                db,
                ticket,
                group_info["assignment_group"],
                actor=user,
                event_token=f"{ticket.id}:agent_assign:{group_info['assignment_group']}",
            )
        except Exception as exc:
            logger.warning("Agent post-confirm assignment notification failed for %s: %s", ticket.ticket_number, exc)

    ticket_loaded = (
        db.query(Ticket)
        .options(joinedload(Ticket.requester), joinedload(Ticket.group))
        .filter(Ticket.id == ticket.id)
        .first()
    )
    return {
        "confirmation_id": pending.confirmation_id,
        "status": "confirmed",
        "ticket": serialize_ticket(ticket_loaded or ticket),
        "escalation": escalation_dict,
    }


def _create_escalation_record(
    db: Session,
    user: User,
    ticket: Optional[Ticket],
    conversation_id: Optional[int],
    group_id: Optional[int],
    group_name: str,
    summary: str,
    attempted_steps: List[str],
    retrieved_sources: List[Dict[str, Any]],
    ip: Optional[str] = None,
) -> AgentEscalation:
    conv_excerpt = _format_conversation_excerpt(db, conversation_id)
    if not attempted_steps and conversation_id:
        attempted_steps = _extract_troubleshooting_from_db(db, conversation_id)

    now = _utc_now()
    esc = AgentEscalation(
        ticket_id=ticket.id if ticket else None,
        conversation_id=conversation_id,
        user_id=user.id,
        recommended_group_id=group_id,
        recommended_group_name=group_name,
        escalation_summary=summary,
        attempted_troubleshooting=_json_dumps_safe(attempted_steps),
        relevant_conversation=conv_excerpt,
        retrieved_references=_json_dumps_safe(retrieved_sources),
        status="routed",
        created_at=now,
    )
    db.add(esc)
    db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            action="ESCALATE_TO_HUMAN",
            resource_type="escalation",
            resource_id=str(esc.id),
            details=(
                f"Escalated to {group_name}"
                + (f" for {ticket.ticket_number}" if ticket else "")
            ),
            ip_address=ip,
            created_at=now,
        )
    )
    return esc


# ---------------------------------------------------------------------------
# Tool 8: escalate_to_human
# ---------------------------------------------------------------------------
def tool_escalate_to_human(
    db: Session,
    user: User,
    reason: str,
    conversation_id: Optional[int] = None,
    ticket_id: Optional[int] = None,
    attempted_troubleshooting: Optional[List[str]] = None,
    retrieved_sources: Optional[List[Dict[str, Any]]] = None,
    recommended_group: Optional[str] = None,
    ip: Optional[str] = None,
) -> Dict[str, Any]:
    cleaned_reason = (reason or "").strip()
    if len(cleaned_reason) < 5:
        raise AgentValidationError("Escalation reason must be at least 5 characters.")

    ticket: Optional[Ticket] = None
    if ticket_id is not None:
        ticket = (
            db.query(Ticket)
            .options(joinedload(Ticket.requester), joinedload(Ticket.group))
            .filter(Ticket.id == ticket_id)
            .first()
        )
        if not ticket or (user.role != "admin" and ticket.requester_id != user.id):
            raise AgentSafetyError("Ticket not found or you are not authorized to escalate it.")

    category_hint = ticket.category if ticket else tool_classify_incident(db, user, cleaned_reason)["category_value"]
    group_info = tool_recommend_assignment_group(db, user, category_hint, preferred_group=recommended_group)

    now = _utc_now()
    if ticket and group_info.get("group_id") and ticket.group_id != group_info["group_id"]:
        old_group = ticket.group.name if ticket.group else None
        ticket.group_id = group_info["group_id"]
        if ticket.status == "open":
            ticket.status = "assigned"
            db.add(
                TicketHistory(
                    ticket_id=ticket.id,
                    user_id=user.id,
                    field_changed="status",
                    old_value="open",
                    new_value="assigned",
                    created_at=now,
                )
            )
        db.add(
            TicketHistory(
                ticket_id=ticket.id,
                user_id=user.id,
                field_changed="assigned_group",
                old_value=old_group,
                new_value=group_info["assignment_group"],
                created_at=now,
            )
        )
        ticket.updated_at = now

    steps = list(attempted_troubleshooting or [])
    if not steps and conversation_id:
        steps = _extract_troubleshooting_from_db(db, conversation_id)

    sources = list(retrieved_sources or [])
    if not sources:
        rag = retrieve_relevant_context(cleaned_reason, top_k=3)
        sources = [
            {
                "filename": c.source_filename,
                "title": c.title,
                "page_number": c.page_number,
                "score": round(c.score, 4),
            }
            for c in rag.chunks
        ]

    esc = _create_escalation_record(
        db=db,
        user=user,
        ticket=ticket,
        conversation_id=conversation_id,
        group_id=group_info.get("group_id"),
        group_name=group_info["assignment_group"],
        summary=cleaned_reason,
        attempted_steps=steps,
        retrieved_sources=sources,
        ip=ip,
    )
    db.commit()
    db.refresh(esc)
    return serialize_escalation(esc)


# ---------------------------------------------------------------------------
# Controlled Tool Registry & Execution Dispatcher
# ---------------------------------------------------------------------------
_TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "search_knowledge_base": tool_search_knowledge_base,
    "classify_incident": tool_classify_incident,
    "recommend_priority": tool_recommend_priority,
    "recommend_assignment_group": tool_recommend_assignment_group,
    "get_ticket_status": tool_get_ticket_status,
    "prepare_ticket": tool_prepare_ticket,
    "create_ticket_after_confirmation": tool_create_ticket_after_confirmation,
    "escalate_to_human": tool_escalate_to_human,
}


def execute_agent_tool(
    db: Session,
    user: User,
    tool_name: str,
    params: Dict[str, Any],
    conversation_id: Optional[int] = None,
    ip: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Central validated tool dispatcher enforcing:
    - Forbidden automation blocks (never auto-close/delete/unconfirmed-create)
    - Tool allow-list check
    - Execution timing, audit logging, and graceful error handling
    """
    started = time.perf_counter()
    input_preview = _json_dumps_safe(params)[:500]

    if tool_name in FORBIDDEN_AUTO_TOOLS:
        elapsed = int((time.perf_counter() - started) * 1000)
        msg = f"Action '{tool_name}' is blocked by Human-in-the-Loop safety rules."
        db.add(
            AgentToolLog(
                conversation_id=conversation_id,
                user_id=user.id,
                tool_name=tool_name,
                status="blocked",
                input_summary=input_preview,
                output_summary=msg,
                execution_ms=elapsed,
            )
        )
        db.add(
            AuditLog(
                user_id=user.id,
                action="AGENT_TOOL_BLOCKED",
                resource_type="agent_tool",
                resource_id=tool_name,
                details=msg,
                ip_address=ip,
            )
        )
        db.commit()
        raise AgentSafetyError(msg)

    fn = _TOOL_REGISTRY.get(tool_name)
    if not fn:
        raise AgentValidationError(f"Unknown or unavailable agent tool: '{tool_name}'.")

    try:
        call_kwargs = dict(params)
        if tool_name in {"create_ticket_after_confirmation", "escalate_to_human"}:
            call_kwargs.setdefault("ip", ip)
        result = fn(db, user, **call_kwargs)
        elapsed = int((time.perf_counter() - started) * 1000)

        log_status = "pending_confirmation" if tool_name == "prepare_ticket" else "success"
        output_preview = _json_dumps_safe(
            {k: v for k, v in result.items() if k not in {"retrieval_result", "context_text"}}
            if isinstance(result, dict)
            else result
        )[:500]

        db.add(
            AgentToolLog(
                conversation_id=conversation_id,
                user_id=user.id,
                tool_name=tool_name,
                status=log_status,
                input_summary=input_preview,
                output_summary=output_preview,
                execution_ms=elapsed,
            )
        )
        db.commit()

        summary_str = f"Executed {tool_name}"
        if tool_name == "search_knowledge_base":
            summary_str = f"Searched KB: {result.get('retained_count', 0)} chunk(s) matched"
        elif tool_name == "classify_incident":
            summary_str = f"Classified as {result.get('category')} ({result.get('recommended_priority')})"
        elif tool_name == "recommend_priority":
            summary_str = f"Priority {result.get('priority_label')} (SLA {result.get('sla_resolution_hours')}h)"
        elif tool_name == "recommend_assignment_group":
            summary_str = f"Recommended team: {result.get('assignment_group')}"
        elif tool_name == "get_ticket_status":
            summary_str = f"Checked {result.get('count', 0)} ticket(s)"
        elif tool_name == "prepare_ticket":
            summary_str = f"Prepared ticket preview for {result.get('assignment_group')} (awaiting confirmation)"
        elif tool_name == "create_ticket_after_confirmation":
            summary_str = f"Created {result['ticket']['ticket_number']} -> {result['ticket'].get('assigned_group')}"
        elif tool_name == "escalate_to_human":
            summary_str = f"Escalated #{result['id']} to {result['recommended_group_name']}"

        return {
            "tool_name": tool_name,
            "status": log_status,
            "summary": summary_str,
            "execution_ms": elapsed,
            "result": result,
        }
    except (AgentSafetyError, AgentValidationError, DuplicateAgentActionError) as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        db.add(
            AgentToolLog(
                conversation_id=conversation_id,
                user_id=user.id,
                tool_name=tool_name,
                status="error",
                input_summary=input_preview,
                output_summary=str(exc)[:500],
                execution_ms=elapsed,
            )
        )
        db.commit()
        raise
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        logger.error("Agent tool '%s' failed: %s", tool_name, str(exc), exc_info=True)
        db.add(
            AgentToolLog(
                conversation_id=conversation_id,
                user_id=user.id,
                tool_name=tool_name,
                status="error",
                input_summary=input_preview,
                output_summary=str(exc)[:500],
                execution_ms=elapsed,
            )
        )
        db.commit()
        raise AgentValidationError(f"Tool '{tool_name}' failed: {str(exc)}") from exc
