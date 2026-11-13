from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_admin
from app.database.session import get_db
from app.models.assignment_group import AssignmentGroup
from app.models.ticket import Ticket, TicketComment, TicketHistory
from app.models.user import User
from app.schemas.ticket import (
    AssignmentGroupOut,
    TicketCommentCreate,
    TicketCommentOut,
    TicketCreate,
    TicketHistoryOut,
    TicketListOut,
    TicketOut,
    TicketUpdate,
)
from app.services.tickets.rules import Category, Priority, Status
from app.services.tickets.service import (
    TicketRuleError,
    as_utc,
    create_ticket,
    serialize_ticket,
    update_ticket,
)

router = APIRouter(prefix="/tickets", tags=["Tickets"])
groups_router = APIRouter(prefix="/assignment-groups", tags=["Assignment Groups"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _get_accessible_ticket(db: Session, ticket_id: int, user: User) -> Ticket:
    """Employees only see their own tickets; a foreign ticket is reported as 404."""
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.requester), joinedload(Ticket.group))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket or (user.role != "admin" and ticket.requester_id != user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket_endpoint(
    payload: TicketCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = {
        "title": payload.title,
        "description": payload.description,
        "category": payload.category.value,
        "subcategory": payload.subcategory,
        "impact": payload.impact.value,
        "urgency": payload.urgency.value,
    }
    ticket = create_ticket(
        db,
        current_user,
        data,
        ip=_client_ip(request),
        background_tasks=background_tasks,
    )
    return serialize_ticket(ticket)


@router.get("", response_model=TicketListOut)
def list_tickets(
    q: Optional[str] = Query(None, max_length=100, description="Search title, description, ticket number, requester"),
    status_filter: Optional[Status] = Query(None, alias="status"),
    priority: Optional[Priority] = None,
    category: Optional[Category] = None,
    group_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Ticket).options(joinedload(Ticket.requester), joinedload(Ticket.group))

    if current_user.role != "admin":
        query = query.filter(Ticket.requester_id == current_user.id)

    if q and q.strip():
        like = f"%{q.strip()}%"
        conditions = [
            Ticket.title.ilike(like),
            Ticket.description.ilike(like),
            Ticket.ticket_number.ilike(like),
        ]
        if current_user.role == "admin":
            conditions.append(Ticket.requester.has(User.name.ilike(like)))
        query = query.filter(or_(*conditions))
    if status_filter:
        query = query.filter(Ticket.status == status_filter.value)
    if priority:
        query = query.filter(Ticket.priority == priority.value)
    if category:
        query = query.filter(Ticket.category == category.value)
    if group_id is not None:
        query = query.filter(Ticket.group_id == group_id)

    total = query.count()
    rows = (
        query.order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serialize_ticket(t) for t in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return serialize_ticket(_get_accessible_ticket(db, ticket_id, current_user))


@router.patch("/{ticket_id}", response_model=TicketOut)
def patch_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_accessible_ticket(db, ticket_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    # Enum members -> plain values
    for key in ("category", "impact", "urgency", "status"):
        if key in changes and changes[key] is not None:
            changes[key] = changes[key].value
    # Non-nullable columns cannot be cleared
    for key in ("title", "description", "category", "impact", "urgency", "status"):
        if key in changes and changes[key] is None:
            raise HTTPException(status_code=422, detail=f"'{key}' cannot be null")

    if current_user.role != "admin":
        # Employees may only close their own already-resolved ticket.
        only_close = set(changes) == {"status"} and changes["status"] == "closed"
        if not only_close:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employees may only close their own resolved tickets.",
            )
        if ticket.status != "resolved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only resolved tickets can be closed by the requester.",
            )

    try:
        update_ticket(
            db,
            ticket,
            current_user,
            changes,
            ip=_client_ip(request),
            background_tasks=background_tasks,
        )
    except TicketRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return serialize_ticket(ticket)


@router.get("/{ticket_id}/history", response_model=List[TicketHistoryOut])
def get_ticket_history(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_accessible_ticket(db, ticket_id, current_user)
    rows = (
        db.query(TicketHistory)
        .options(joinedload(TicketHistory.user))
        .filter(TicketHistory.ticket_id == ticket_id)
        .order_by(TicketHistory.created_at.asc(), TicketHistory.id.asc())
        .all()
    )
    return [
        {
            "id": h.id,
            "ticket_id": h.ticket_id,
            "field_changed": h.field_changed,
            "old_value": h.old_value,
            "new_value": h.new_value,
            "changed_by": h.user.name if h.user else None,
            "changed_by_id": h.user_id,
            "created_at": as_utc(h.created_at),
        }
        for h in rows
    ]


@router.get("/{ticket_id}/comments", response_model=List[TicketCommentOut])
def list_ticket_comments(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List scoped comments/replies on an accessible ticket."""
    _get_accessible_ticket(db, ticket_id, current_user)
    rows = (
        db.query(TicketComment)
        .options(joinedload(TicketComment.author))
        .filter(TicketComment.ticket_id == ticket_id)
        .order_by(TicketComment.created_at.asc(), TicketComment.id.asc())
        .all()
    )
    return [
        {
            "id": c.id,
            "ticket_id": c.ticket_id,
            "author_id": c.author_id,
            "author_name": c.author.name if c.author else "User",
            "author_role": c.author.role if c.author else "employee",
            "message": c.message,
            "created_at": as_utc(c.created_at),
        }
        for c in rows
    ]


@router.post("/{ticket_id}/comments", response_model=TicketCommentOut, status_code=status.HTTP_201_CREATED)
def add_ticket_comment(
    ticket_id: int,
    payload: TicketCommentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an employee reply or administrator response to a ticket and emit persistent notifications."""
    ticket = _get_accessible_ticket(db, ticket_id, current_user)
    comment = TicketComment(
        ticket_id=ticket.id,
        author_id=current_user.id,
        message=payload.message,
    )
    db.add(comment)
    db.add(
        TicketHistory(
            ticket_id=ticket.id,
            user_id=current_user.id,
            field_changed="comment",
            old_value=None,
            new_value=payload.message[:250],
        )
    )
    ticket.updated_at = comment.created_at or as_utc(ticket.updated_at)
    db.commit()
    db.refresh(comment)

    try:
        from app.services.notifications.notification_service import notify_ticket_comment

        notify_ticket_comment(
            db,
            ticket,
            comment.message,
            author=current_user,
            comment_id=comment.id,
            background_tasks=background_tasks,
        )
    except Exception:
        pass

    return {
        "id": comment.id,
        "ticket_id": comment.ticket_id,
        "author_id": comment.author_id,
        "author_name": current_user.name,
        "author_role": current_user.role,
        "message": comment.message,
        "created_at": as_utc(comment.created_at),
    }


@groups_router.get("", response_model=List[AssignmentGroupOut])
def list_assignment_groups(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return db.query(AssignmentGroup).order_by(AssignmentGroup.name).all()
