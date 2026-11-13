import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.services.agent.orchestrator import run_agentic_chat_workflow
from app.services.llm.groq_client import (
    GroqAuthenticationError,
    GroqClientError,
    GroqRateLimitError,
    groq_client,
)
from app.services.llm.prompt_manager import build_chat_messages
from app.services.llm.response_handler import ResponseHandler
from app.services.llm.schemas import ActionItem, ChatRequest, ChatResponse
from app.services.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])


def _client_ip(request: Optional[Request]) -> Optional[str]:
    return request.client.host if request and request.client else None


@router.post("", response_model=ChatResponse)
async def chat_with_ai(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    POST /api/chat
    Agentic + RAG Generative AI endpoint:
    1. Persist user message & load conversation history.
    2. Run controlled backend orchestration tools (KB search, classification, priority, group routing, ticket status / preparation).
    3. Build grounded system prompt with retrieved KB docs + agent tool context.
    4. Query Groq LLM and return response with sources, tool calls, and Human-in-the-Loop pending ticket confirmation if triggered.
    """
    user_msg_text = payload.message.strip()
    if not user_msg_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Message content cannot be blank.",
        )

    # 1. Fetch or initialize conversation owned by current_user
    conversation = None
    if payload.conversation_id:
        try:
            cid = int(payload.conversation_id)
            conversation = (
                db.query(Conversation)
                .filter(
                    Conversation.id == cid,
                    Conversation.user_id == current_user.id,
                )
                .first()
            )
        except ValueError:
            conversation = None

    if not conversation:
        conversation = Conversation(user_id=current_user.id, ticket_id=None)
        db.add(conversation)
        db.flush()

    conv_id = str(conversation.id)

    # 2. Persist user message
    user_msg_record = Message(
        conversation_id=conversation.id,
        sender_type="user",
        sender_id=current_user.id,
        content=user_msg_text,
    )
    db.add(user_msg_record)
    db.commit()

    # 3. Assemble prior conversation history
    past_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )

    formatted_history: List[Dict[str, str]] = []
    for m in past_messages[:-1]:
        role = "user" if m.sender_type == "user" else "assistant"
        formatted_history.append({"role": role, "content": m.content})

    # 4. Run Agentic Tool Workflow (search_knowledge_base, classify, recommend, prepare_ticket / status check)
    orchestrated = run_agentic_chat_workflow(
        db=db,
        user=current_user,
        conversation=conversation,
        user_message=user_msg_text,
        formatted_history=formatted_history,
        ip=_client_ip(request),
    )
    retrieval_result: RetrievalResult = orchestrated["retrieval_result"]
    tool_calls = orchestrated["tool_calls"]
    pending_action = orchestrated["pending_action"]
    agent_context_block: str = orchestrated["agent_context_block"]

    # Combine KB excerpts + agent orchestration state into grounded context
    combined_context_parts = []
    if retrieval_result.context_text:
        combined_context_parts.append(retrieval_result.context_text)
    if agent_context_block:
        combined_context_parts.append(agent_context_block)
    combined_context = "\n\n".join(combined_context_parts) or None

    # 5. Construct RAG-grounded prompt messages
    llm_input_messages = build_chat_messages(
        history=formatted_history,
        new_message=user_msg_text,
        context=combined_context,
        has_relevant_docs=retrieval_result.has_relevant_docs,
    )

    # 6. Call Groq LLM with graceful error handling
    try:
        raw_ai_response = await groq_client.chat_completion(llm_input_messages)
        ai_response_text = ResponseHandler.validate_and_clean_response(raw_ai_response)
    except GroqAuthenticationError as e:
        logger.warning("Groq Auth Error: %s", str(e))
        ai_response_text = (
            "**NexDesk AI Service Notice:** The Groq AI API key is currently unconfigured or expired. "
            "Please check the server environment configuration (GROQ_API_KEY) in Settings to restore full AI assistance."
        )
    except GroqRateLimitError as e:
        logger.warning("Groq Rate Limit: %s", str(e))
        ai_response_text = (
            "The AI support system is currently receiving a high volume of requests. "
            "Please wait a moment before asking another question, or raise an IT ticket directly."
        )
    except GroqClientError as e:
        logger.error("Groq Client Error: %s", str(e))
        ai_response_text = (
            f"An error occurred while communicating with the AI service: {str(e)}. "
            "Our support team has been notified. You can still create an incident manually."
        )

    # 7. Attach real verified ChromaDB sources + suggested actions + follow-up questions
    sources, actions, follow_up_questions = ResponseHandler.extract_rag_outputs(
        user_msg_text, ai_response_text, retrieval_result
    )

    if pending_action is not None:
        confirm_action = ActionItem(
            action_type="confirm_ticket",
            label=f"Review & Confirm Ticket ({pending_action.recommended_priority})",
            payload={"confirmation_id": pending_action.confirmation_id},
        )
        actions = [confirm_action] + actions

    # 8. Persist assistant message
    assistant_msg_record = Message(
        conversation_id=conversation.id,
        sender_type="agent",
        sender_id=None,
        content=ai_response_text,
    )
    db.add(assistant_msg_record)
    db.commit()

    return ChatResponse(
        conversation_id=conv_id,
        response=ai_response_text,
        sources=sources,
        actions=actions,
        follow_up_questions=follow_up_questions,
        rag_used=retrieval_result.has_relevant_docs,
        retrieved_chunks_count=retrieval_result.retained_count,
        tool_calls=tool_calls,
        pending_action=pending_action,
    )
