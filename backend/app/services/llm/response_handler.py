import re
from typing import Dict, List, Optional, Tuple

from app.services.llm.schemas import ActionItem, SourceReference
from app.services.rag.retriever import RetrievalResult

CATEGORY_RULES: List[Tuple[str, List[str], str]] = [
    ("network", ["vpn", "wifi", "wi-fi", "dns", "gateway", "proxy", "firewall", "network", "504", "403"], "VPN / Connectivity"),
    ("access_management", ["password", "okta", "mfa", "2fa", "yubikey", "token", "sso", "login", "locked", "access"], "Account & Access"),
    ("security", ["phishing", "malware", "virus", "bitlocker", "encryption", "certificate", "security", "breach"], "Security"),
    ("email", ["outlook", "email", "mailbox", "exchange", "calendar", "smtp"], "Email & Collaboration"),
    ("hardware", ["laptop", "monitor", "dock", "thunderbolt", "keyboard", "mouse", "printer", "battery", "display", "screen"], "Device Hardware"),
    ("software", ["docker", "wsl", "excel", "teams", "zoom", "slack", "install", "update", "crash", "software"], "Application Software"),
]


def _truncate_excerpt(text: str, max_len: int = 240) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def _infer_ticket_metadata(
    user_message: str,
    raw_response: str,
    retrieval_result: Optional[RetrievalResult] = None,
) -> Dict[str, str]:
    valid_categories = {
        "hardware",
        "software",
        "network",
        "access_management",
        "email",
        "security",
        "other",
    }

    if retrieval_result and retrieval_result.chunks:
        top_cat = (retrieval_result.chunks[0].category or "").strip().lower()
        if top_cat in valid_categories:
            return {"category": top_cat, "subcategory": retrieval_result.chunks[0].title[:60]}

    combined = f"{user_message} {raw_response}".lower()
    for category, keywords, subcategory in CATEGORY_RULES:
        if any(kw in combined for kw in keywords):
            return {"category": category, "subcategory": subcategory}

    return {"category": "other", "subcategory": "General IT Support"}


class ResponseHandler:
    @staticmethod
    def build_sources_from_retrieval(
        retrieval_result: Optional[RetrievalResult],
        max_sources: int = 4,
    ) -> List[SourceReference]:
        """
        Converts actual retrieved ChromaDB chunks into verified SourceReference items.
        Never fabricates unretrieved citations.
        """
        if not retrieval_result or not retrieval_result.chunks:
            return []

        sources: List[SourceReference] = []
        seen_keys: set[Tuple[int, int]] = set()

        for chunk in retrieval_result.chunks:
            dedupe_key = (chunk.document_id, chunk.page_number)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            sources.append(
                SourceReference(
                    id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    filename=chunk.source_filename,
                    title=chunk.title,
                    page_number=chunk.page_number,
                    score=round(chunk.score, 4),
                    category=chunk.category,
                    snippet=_truncate_excerpt(chunk.text),
                )
            )
            if len(sources) >= max_sources:
                break

        return sources

    @staticmethod
    def build_actions_and_followups(
        user_message: str,
        raw_response: str,
        retrieval_result: Optional[RetrievalResult] = None,
    ) -> Tuple[List[ActionItem], List[str]]:
        """
        Generates contextual troubleshooting actions, a prefilled Create Ticket action,
        and tailored follow-up questions grounded in the query & retrieval outcome.
        """
        meta = _infer_ticket_metadata(user_message, raw_response, retrieval_result)
        category = meta["category"]
        subcategory = meta["subcategory"]
        has_docs = bool(retrieval_result and retrieval_result.has_relevant_docs)

        clean_title = " ".join(user_message.strip().split())
        if len(clean_title) > 90:
            clean_title = clean_title[:87].rstrip() + "..."
        if len(clean_title) < 5:
            clean_title = f"IT Support Request: {subcategory}"

        description_lines = [
            f"Reported issue: {user_message.strip()}",
            "",
            "AI Troubleshooting Summary:",
            _truncate_excerpt(raw_response, 400),
        ]
        if has_docs and retrieval_result:
            refs = ", ".join(
                f"{c.source_filename} (p.{c.page_number})" for c in retrieval_result.chunks[:3]
            )
            description_lines.append(f"\nReferenced KB Docs: {refs}")

        impact = "high" if category in {"network", "security"} else "medium"
        urgency = "high" if any(w in user_message.lower() for w in ["urgent", "blocked", "cannot", "down", "error", "outage"]) else "medium"

        actions: List[ActionItem] = []

        if has_docs and retrieval_result:
            top_chunk = retrieval_result.chunks[0]
            actions.append(
                ActionItem(
                    action_type="suggested_step",
                    label=f"Open {top_chunk.source_filename} (Page {top_chunk.page_number})",
                    payload={
                        "document_id": top_chunk.document_id,
                        "filename": top_chunk.source_filename,
                        "page_number": top_chunk.page_number,
                    },
                )
            )
        else:
            actions.append(
                ActionItem(
                    action_type="suggested_step",
                    label="Browse Knowledge Base",
                    payload={"route": "/knowledge-base"},
                )
            )

        actions.append(
            ActionItem(
                action_type="create_ticket",
                label="Create IT Ticket" if has_docs else "Escalate via IT Ticket",
                payload={
                    "title": clean_title,
                    "description": "\n".join(description_lines),
                    "category": category,
                    "subcategory": subcategory,
                    "impact": impact,
                    "urgency": urgency,
                },
            )
        )

        # Follow-up question chips
        follow_ups: List[str] = []
        if has_docs:
            if category == "network":
                follow_ups = [
                    "Which exact error code or gateway URL should I check?",
                    "I tried those steps and still cannot connect — what next?",
                    "Do I need a certificate or client reinstall?",
                ]
            elif category in {"access_management", "security"}:
                follow_ups = [
                    "What approval is needed for a temporary MFA bypass or reset?",
                    "How long does password or token propagation take?",
                    "I am still locked out after resetting — how do I escalate?",
                ]
            else:
                follow_ups = [
                    "Can you walk me through these steps for Windows 11?",
                    "What logs or screenshots should I collect before escalating?",
                    "If this does not resolve it, which team should handle the ticket?",
                ]
        else:
            follow_ups = [
                "Which IT team owns this policy or system?",
                "What troubleshooting details should I include in a support ticket?",
                "Can you search Knowledge Base procedures for related issues?",
            ]

        return actions, follow_ups

    @staticmethod
    def extract_rag_outputs(
        user_message: str,
        raw_response: str,
        retrieval_result: Optional[RetrievalResult] = None,
    ) -> Tuple[List[SourceReference], List[ActionItem], List[str]]:
        sources = ResponseHandler.build_sources_from_retrieval(retrieval_result)
        actions, follow_ups = ResponseHandler.build_actions_and_followups(
            user_message, raw_response, retrieval_result
        )
        return sources, actions, follow_ups

    @staticmethod
    def validate_and_clean_response(raw_text: str) -> str:
        """
        Cleans up raw markdown or model reasoning tags if emitted.
        """
        if not raw_text:
            return "I received your message, but the generated response was empty. Please try rephrasing your question."

        cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        return cleaned or raw_text.strip()
