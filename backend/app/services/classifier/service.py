"""
AI-Powered Incident Classification Service.
Uses Groq LLM with robust prompt engineering and JSON mode extraction,
coupled with an intelligent local heuristic fallback and deterministic backend priority rules.
"""
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from app.services.classifier.rules import (
    CATEGORY_DISPLAY_LABELS,
    evaluate_priority_matrix,
    normalize_category,
    normalize_level,
    resolve_assignment_group,
)
from app.services.classifier.schemas import (
    IncidentClassificationRequest,
    IncidentClassificationResponse,
)
from app.services.llm.groq_client import (
    GroqAuthenticationError,
    GroqClientError,
    groq_client,
)

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """You are NexDesk AI Incident Classifier, an expert enterprise ITSM triage engine.
Your task is to analyze employee IT issue descriptions written in natural language and extract structured incident classification signals.

Supported Categories:
- Hardware (laptops, monitors, keyboards, docks, printers, mice, chargers, physical components)
- Software (operating system, desktop apps, Excel, Teams, Zoom, Slack, Docker, IDE, crashes, license errors)
- Network (Wi-Fi, VPN, LAN, Internet, DNS, proxy, routing, slow connection, gateway timeout)
- Access Management (password reset, Okta, MFA, 2FA, YubiKey, SSO, account locked, permission grants)
- Email (Outlook, Exchange, shared mailbox, calendar invites, bounced emails, spam)
- Security (phishing, virus, malware, BitLocker recovery key, suspicious alert, data leakage, unauthorized access)
- Other (general workplace IT inquiries not covered above)

Supported Assignment Groups:
- Hardware Support
- Network Support
- Software Support
- Security Support
- Access Management

Impact levels:
- High (widespread outage, multiple teams blocked, critical business system down)
- Medium (a team, department, or important service affected; moderate disruption)
- Low (single user affected or non-critical minor service issue)

Urgency levels:
- High (user or team is completely blocked right now with no workaround; time-sensitive)
- Medium (significant degradation or work impaired, but a partial workaround exists)
- Low (inconvenience, cosmetic issue, or can wait for normal scheduling)

Output format:
Return ONLY valid JSON with exactly the following keys:
{
  "title": "Concise professional title under 60 chars",
  "category": "One of: Hardware, Software, Network, Access Management, Email, Security, Other",
  "subcategory": "Specific subcomponent, e.g. Wi-Fi, VPN, Monitor, Dock, Outlook, MFA",
  "impact": "High, Medium, or Low",
  "urgency": "High, Medium, or Low",
  "recommended_priority": "P1, P2, P3, or P4",
  "assignment_group": "One of: Hardware Support, Network Support, Software Support, Security Support, Access Management",
  "summary": "One-sentence executive summary of the incident",
  "recommended_action": "Actionable immediate triage or troubleshooting advice",
  "signals": "Brief reason for chosen impact and urgency"
}
Do NOT include markdown backticks or commentary outside the JSON object.
"""

# Intelligent keyword signals for local fallback if Groq API is unavailable or offline
HEURISTIC_RULES = [
    {
        "category": "network",
        "subcategory": "Wi-Fi",
        "keywords": ["wi-fi", "wifi", "wireless", "ssid", "wlan"],
        "assignment_group": "Network Support",
        "default_impact": "medium",
        "default_urgency": "high",
        "action": "Verify network configuration, adapter drivers, and corporate wireless credentials.",
    },
    {
        "category": "network",
        "subcategory": "VPN",
        "keywords": ["vpn", "globalprotect", "openvpn", "tunnel", "gateway", "504"],
        "assignment_group": "Network Support",
        "default_impact": "high",
        "default_urgency": "high",
        "action": "Verify VPN gateway status, flush DNS cache, and check SAML authentication.",
    },
    {
        "category": "hardware",
        "subcategory": "Docking Station",
        "keywords": ["dock", "thunderbolt", "wd19", "flicker", "flickering"],
        "assignment_group": "Hardware Support",
        "default_impact": "medium",
        "default_urgency": "medium",
        "action": "Power-drain docking station for 30s and test with certified DisplayPort cable.",
    },
    {
        "category": "hardware",
        "subcategory": "Laptop & Peripherals",
        "keywords": ["laptop", "battery", "charger", "screen", "keyboard", "mouse", "monitor", "display", "printer"],
        "assignment_group": "Hardware Support",
        "default_impact": "low",
        "default_urgency": "medium",
        "action": "Run hardware diagnostics and schedule device inspection or replacement.",
    },
    {
        "category": "access_management",
        "subcategory": "Password & Authentication",
        "keywords": ["password", "reset", "locked", "login", "account", "okta", "sso"],
        "assignment_group": "Access Management",
        "default_impact": "low",
        "default_urgency": "high",
        "action": "Initiate self-service password reset or verify employee ID for account unlock.",
    },
    {
        "category": "access_management",
        "subcategory": "MFA & Security Token",
        "keywords": ["yubikey", "mfa", "2fa", "token", "authenticator", "bypass code"],
        "assignment_group": "Access Management",
        "default_impact": "medium",
        "default_urgency": "high",
        "action": "Verify manager authorization and issue temporary MFA bypass code.",
    },
    {
        "category": "security",
        "subcategory": "Incident Response",
        "keywords": ["phishing", "virus", "malware", "ransomware", "hacked", "breach", "suspicious email", "bitlocker"],
        "assignment_group": "Security Support",
        "default_impact": "high",
        "default_urgency": "high",
        "action": "Isolate affected endpoint from network immediately and perform security triage.",
    },
    {
        "category": "email",
        "subcategory": "Email & Calendar",
        "keywords": ["outlook", "email", "mailbox", "exchange", "calendar", "smtp"],
        "assignment_group": "Software Support",
        "default_impact": "low",
        "default_urgency": "medium",
        "action": "Check Microsoft 365 tenant service health and rebuild Outlook local profile.",
    },
    {
        "category": "software",
        "subcategory": "Application Software",
        "keywords": ["docker", "wsl", "teams", "excel", "zoom", "slack", "crash", "install", "update", "license"],
        "assignment_group": "Software Support",
        "default_impact": "low",
        "default_urgency": "medium",
        "action": "Clear local application cache, restart service, or reinstall client package.",
    },
]


def _clean_json_output(raw_text: str) -> str:
    """Extracts JSON substring from markdown backticks or surrounding text."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    # Strip markdown fenced code blocks if present
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Or find first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()
    return text


def _heuristic_classification(description: str) -> Dict[str, Any]:
    """Generates structured classification heuristics when LLM is unconfigured or unavailable."""
    desc_lower = description.lower()
    matched_rule = None
    for rule in HEURISTIC_RULES:
        if any(kw in desc_lower for kw in rule["keywords"]):
            matched_rule = rule
            break

    if not matched_rule:
        matched_rule = {
            "category": "other",
            "subcategory": "General IT",
            "assignment_group": "Tier 1 Service Desk",
            "default_impact": "medium",
            "default_urgency": "medium",
            "action": "Gather detailed logs, error codes, and assign to frontline IT triage.",
        }

    # Extract clean concise title
    first_sentence = description.split(".")[0].strip()
    title = first_sentence[:60] if len(first_sentence) >= 10 else f"{matched_rule['subcategory']} Incident"
    if len(title) > 60:
        title = title[:57].rstrip() + "..."

    # Check urgency signals
    urgency = matched_rule["default_urgency"]
    if any(w in desc_lower for w in ["blocked", "urgent", "down", "outage", "stopped", "cannot work", "immediately"]):
        urgency = "high"

    impact = matched_rule["default_impact"]
    if any(w in desc_lower for w in ["all users", "entire team", "company-wide", "production", "multiple users"]):
        impact = "high"

    return {
        "title": title,
        "category": CATEGORY_DISPLAY_LABELS.get(matched_rule["category"], "Other"),
        "subcategory": matched_rule["subcategory"],
        "impact": impact.capitalize(),
        "urgency": urgency.capitalize(),
        "recommended_priority": "P2" if urgency == "high" and impact == "medium" else "P3",
        "assignment_group": matched_rule["assignment_group"],
        "summary": f"Employee reported: {description[:120].strip()}",
        "recommended_action": matched_rule["action"],
        "signals": "Derived from deterministic ITSM heuristic analyzer.",
    }


async def classify_incident_description(
    description: str,
) -> IncidentClassificationResponse:
    """
    Main classifier entrypoint:
    1. Send issue description to Groq LLM for signal extraction.
    2. Fallback to intelligent local rules if LLM is offline.
    3. MANDATORY: Enforce backend deterministic ITIL priority matrix (never trust LLM priority directly).
    4. Deterministically resolve category and assignment group.
    """
    cleaned_desc = description.strip()
    raw_output: Optional[Dict[str, Any]] = None
    confidence_note: str = ""

    if groq_client.is_configured():
        messages = [
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Classify this employee incident description:\n\n{cleaned_desc}"},
        ]
        try:
            llm_text = await groq_client.chat_completion(
                messages,
                temperature=0.2,  # Low temperature for deterministic classification
                max_tokens=500,
            )
            cleaned_json = _clean_json_output(llm_text)
            parsed = json.loads(cleaned_json)
            if isinstance(parsed, dict) and "title" in parsed and "category" in parsed:
                raw_output = parsed
                confidence_note = "Extracted by Groq LLM with deterministic backend validation."
        except (json.JSONDecodeError, GroqClientError, Exception) as exc:
            logger.warning("Groq classification fallback invoked: %s", str(exc))

    if not raw_output:
        raw_output = _heuristic_classification(cleaned_desc)
        confidence_note = "Generated via intelligent local ITSM heuristics (Groq LLM offline or unconfigured)."

    # 1. Normalize Category
    cat_val = normalize_category(str(raw_output.get("category", "")))
    cat_display = CATEGORY_DISPLAY_LABELS.get(cat_val, "Other")

    # 2. Subcategory
    subcat = str(raw_output.get("subcategory") or "").strip() or None

    # 3. Normalize Impact and Urgency signals from LLM/heuristic
    impact_val = normalize_level(str(raw_output.get("impact", "")), default="medium")
    urgency_val = normalize_level(str(raw_output.get("urgency", "")), default="medium")

    # 4. DETERMINISTIC BACKEND PRIORITY ENGINE (Rule enforcement)
    # The LLM's priority suggestion is captured for auditing, but the final priority is strictly evaluated here!
    raw_llm_priority = str(raw_output.get("recommended_priority") or "").strip().upper()
    priority_key, priority_code, priority_label = evaluate_priority_matrix(impact_val, urgency_val)

    # 5. Assignment Group Recommendation
    raw_group = str(raw_output.get("assignment_group") or "").strip()
    assignment_group = resolve_assignment_group(cat_val, raw_group)

    # 6. Title and Summary sanitization
    raw_title = str(raw_output.get("title") or "").strip()
    title = raw_title if len(raw_title) >= 5 else f"{cat_display} Support Request"
    if len(title) > 120:
        title = title[:117].rstrip() + "..."

    summary = str(raw_output.get("summary") or "").strip()
    if not summary:
        summary = f"Employee reported an issue regarding {cat_display.lower()} ({subcat or 'general'})."

    rec_action = str(raw_output.get("recommended_action") or "").strip()
    if not rec_action:
        rec_action = f"Assign to {assignment_group} for standard triage."

    return IncidentClassificationResponse(
        title=title,
        category=cat_display,
        category_value=cat_val,
        subcategory=subcat,
        impact=impact_val.capitalize(),
        impact_value=impact_val,
        urgency=urgency_val.capitalize(),
        urgency_value=urgency_val,
        recommended_priority=priority_code,
        priority_label=priority_label,
        priority_value=priority_key,
        assignment_group=assignment_group,
        summary=summary,
        recommended_action=rec_action,
        raw_llm_priority=raw_llm_priority or priority_code,
        confidence_signals=confidence_note,
    )
