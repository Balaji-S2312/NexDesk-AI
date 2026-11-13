import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.user import User
from app.services.agent.schemas import PendingActionOut, ToolExecutionOut
from app.services.agent.tools import execute_agent_tool
from app.services.rag.retriever import RetrievalResult

UNRESOLVED_PATTERNS = [
    "still not working",
    "didn't work",
    "did not work",
    "does not work",
    "doesn't work",
    "after following",
    "still failing",
    "still broken",
    "still cannot",
    "still can't",
    "not resolved",
    "no luck",
    "tried that",
    "tried those",
    "create a ticket",
    "create ticket",
    "open a ticket",
    "open ticket",
    "raise a ticket",
    "prepare a ticket",
    "log a ticket",
    "escalate",
    "human agent",
    "human technician",
    "support team",
]

STATUS_PATTERNS = [
    "ticket status",
    "status of my ticket",
    "status of ticket",
    "check my ticket",
    "my latest ticket",
    "where is my ticket",
]


def _build_retrieval_query(history: List[Dict[str, str]], new_message: str) -> str:
    """
    Augments short follow-ups or unresolved messages with the prior user problem statement
    so ChromaDB continues retrieving relevant troubleshooting docs.
    """
    words = new_message.strip().split()
    prior_user_msgs = [m["content"] for m in history if m.get("role") == "user" and m.get("content")]
    if prior_user_msgs and (
        len(words) <= 6
        or any(pat in new_message.lower() for pat in UNRESOLVED_PATTERNS)
    ):
        return f"{prior_user_msgs[-1]} {new_message}".strip()
    return new_message.strip()


def _extract_attempted_steps(history: List[Dict[str, str]]) -> List[str]:
    steps: List[str] = []
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        for line in (msg.get("content") or "").splitlines():
            clean = line.strip()
            if re.match(r"^(\d+[\.\)]|[-*])\s+", clean):
                step_text = re.sub(r"^(\d+[\.\)]|[-*])\s+", "", clean).strip()
                if len(step_text) >= 8 and step_text not in steps:
                    steps.append(step_text[:180])
    if not steps and any(m.get("role") == "assistant" for m in history):
        last_agent = [m["content"] for m in history if m.get("role") == "assistant"][-1]
        snippet = " ".join(last_agent.split())[:180]
        if snippet:
            steps.append(snippet)
    return steps[:6]


def detect_agent_intent(user_message: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    lower = (user_message or "").lower()

    inc_match = re.search(r"\b(INC\d{4,10})\b", user_message, re.IGNORECASE)
    ticket_ref = inc_match.group(1).upper() if inc_match else None
    is_status_check = bool(ticket_ref and "status" in lower) or any(
        pat in lower for pat in STATUS_PATTERNS
    )

    is_unresolved_followup = any(pat in lower for pat in UNRESOLVED_PATTERNS)

    prior_user_msgs = [m["content"] for m in history if m.get("role") == "user" and m.get("content")]
    if is_unresolved_followup and prior_user_msgs:
        root_problem = f"{prior_user_msgs[0]} — Follow-up: {user_message.strip()}"
    elif prior_user_msgs and len(user_message.split()) <= 5:
        root_problem = f"{prior_user_msgs[-1]} ({user_message.strip()})"
    else:
        root_problem = user_message.strip()

    attempted_steps = _extract_attempted_steps(history)

    return {
        "is_status_check": is_status_check,
        "ticket_reference": ticket_ref,
        "is_unresolved_followup": is_unresolved_followup,
        "root_problem_description": root_problem,
        "attempted_troubleshooting": attempted_steps,
    }


def _as_tool_out(exec_res: Dict[str, Any], public_data: Optional[Dict[str, Any]] = None) -> ToolExecutionOut:
    return ToolExecutionOut(
        tool_name=exec_res["tool_name"],
        status=exec_res["status"],
        summary=exec_res["summary"],
        execution_ms=exec_res["execution_ms"],
        data=public_data,
    )


def run_agentic_chat_workflow(
    db: Session,
    user: User,
    conversation: Conversation,
    user_message: str,
    formatted_history: List[Dict[str, str]],
    ip: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Python orchestration service coordinating independent ITSM tools with
    Human-in-the-Loop confirmation gates.
    """
    intent = detect_agent_intent(user_message, formatted_history)
    tool_calls: List[ToolExecutionOut] = []
    pending_action: Optional[PendingActionOut] = None
    agent_notes: List[str] = []

    # Step A: Always execute KB search tool first (grounded RAG)
    retrieval_query = _build_retrieval_query(formatted_history, user_message)
    kb_exec = execute_agent_tool(
        db=db,
        user=user,
        tool_name="search_knowledge_base",
        params={"query": retrieval_query, "top_k": 5},
        conversation_id=conversation.id,
        ip=ip,
    )
    kb_result = kb_exec["result"]
    retrieval_result: RetrievalResult = kb_result["retrieval_result"]
    tool_calls.append(
        _as_tool_out(
            kb_exec,
            {
                "rag_used": kb_result["rag_used"],
                "retained_count": kb_result["retained_count"],
            },
        )
    )

    # Step B: If ticket status inquiry, execute authorized get_ticket_status tool
    if intent["is_status_check"]:
        try:
            status_exec = execute_agent_tool(
                db=db,
                user=user,
                tool_name="get_ticket_status",
                params={"ticket_reference": intent["ticket_reference"]},
                conversation_id=conversation.id,
                ip=ip,
            )
            tickets_found = status_exec["result"].get("tickets", [])
            tool_calls.append(_as_tool_out(status_exec, {"count": len(tickets_found)}))
            if tickets_found:
                lines = [
                    f"- {t['ticket_number']}: {t['title']} | Status: {t['status']} | "
                    f"Priority: {t['priority_label']} | Group: {t.get('assigned_group') or 'Unassigned'}"
                    for t in tickets_found
                ]
                agent_notes.append("Live Ticket Status Lookup Results:\n" + "\n".join(lines))
            else:
                agent_notes.append("Ticket Status Lookup: The user has no existing IT tickets.")
        except Exception as exc:
            agent_notes.append(f"Ticket Status Lookup Notice: {str(exc)}")

    # Step C: Run classification, deterministic priority, and group recommendation tools
    problem_text = intent["root_problem_description"]
    cls_exec = execute_agent_tool(
        db=db,
        user=user,
        tool_name="classify_incident",
        params={"description": problem_text},
        conversation_id=conversation.id,
        ip=ip,
    )
    cls_data = cls_exec["result"]
    tool_calls.append(
        _as_tool_out(
            cls_exec,
            {
                "category": cls_data["category"],
                "subcategory": cls_data.get("subcategory"),
                "impact": cls_data["impact"],
                "urgency": cls_data["urgency"],
            },
        )
    )

    prio_exec = execute_agent_tool(
        db=db,
        user=user,
        tool_name="recommend_priority",
        params={"impact": cls_data["impact_value"], "urgency": cls_data["urgency_value"]},
        conversation_id=conversation.id,
        ip=ip,
    )
    prio_data = prio_exec["result"]
    tool_calls.append(
        _as_tool_out(
            prio_exec,
            {
                "recommended_priority": prio_data["recommended_priority"],
                "priority_label": prio_data["priority_label"],
            },
        )
    )

    grp_exec = execute_agent_tool(
        db=db,
        user=user,
        tool_name="recommend_assignment_group",
        params={"category": cls_data["category_value"]},
        conversation_id=conversation.id,
        ip=ip,
    )
    grp_data = grp_exec["result"]
    tool_calls.append(
        _as_tool_out(
            grp_exec,
            {
                "assignment_group": grp_data["assignment_group"],
                "group_id": grp_data.get("group_id"),
            },
        )
    )

    # Step D: When troubleshooting was unsuccessful or user requests escalation/ticket,
    # execute prepare_ticket (NEVER creates a ticket until user explicitly confirms!)
    if intent["is_unresolved_followup"]:
        steps = intent["attempted_troubleshooting"] or [
            "Employee followed prior troubleshooting instructions without resolving the issue."
        ]
        sources_summary = kb_result.get("chunks", [])
        esc_summary = (
            f"Unresolved {cls_data['category']} incident after attempted troubleshooting. "
            f"Recommended routing to {grp_data['assignment_group']} ({prio_data['priority_label']})."
        )
        prep_exec = execute_agent_tool(
            db=db,
            user=user,
            tool_name="prepare_ticket",
            params={
                "description": problem_text,
                "conversation_id": conversation.id,
                "title": cls_data["title"],
                "category": cls_data["category_value"],
                "subcategory": cls_data.get("subcategory"),
                "impact": prio_data["impact_value"],
                "urgency": prio_data["urgency_value"],
                "attempted_troubleshooting": steps,
                "retrieved_sources": sources_summary,
                "escalation_summary": esc_summary,
            },
            conversation_id=conversation.id,
            ip=ip,
        )
        pending_dict = prep_exec["result"]
        pending_action = PendingActionOut(**pending_dict)
        tool_calls.append(
            _as_tool_out(
                prep_exec,
                {
                    "confirmation_id": pending_action.confirmation_id,
                    "status": pending_action.status,
                    "assignment_group": pending_action.assignment_group,
                    "recommended_priority": pending_action.recommended_priority,
                },
            )
        )
        agent_notes.append(
            "HUMAN-IN-THE-LOOP TICKET PREVIEW PREPARED (NOT YET CREATED):\n"
            f"- Confirmation ID: {pending_action.confirmation_id}\n"
            f"- Prepared Title: {pending_action.title}\n"
            f"- Category: {pending_action.category}\n"
            f"- Priority (Backend Matrix): {pending_action.priority_label}\n"
            f"- Recommended Assignment Group: {pending_action.assignment_group}\n"
            "- Instructions for Assistant: Inform the employee that troubleshooting did not resolve the issue, "
            "present the prepared ticket summary above, and ask them to click 'Confirm & Create Ticket' in the "
            "Ticket Preview card below to submit it to the human team. DO NOT claim the ticket is already created."
        )

    return {
        "retrieval_result": retrieval_result,
        "tool_calls": tool_calls,
        "pending_action": pending_action,
        "agent_context_block": "\n\n".join(agent_notes),
    }
