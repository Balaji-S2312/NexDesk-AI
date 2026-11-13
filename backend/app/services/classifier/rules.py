"""
Deterministic ITIL assignment and priority rules for AI-powered Incident Classification.
Guarantees that unvalidated LLM output never directly bypasses backend business rules.
"""
from typing import Dict, Optional, Tuple
from app.services.tickets.rules import (
    Category,
    Impact,
    Urgency,
    Priority,
    PRIORITY_LABELS,
    calculate_priority,
)

# Canonical mapping from supported ITSM incident categories to default assignment groups
CATEGORY_ASSIGNMENT_MAP: Dict[str, str] = {
    Category.hardware.value: "Hardware Support",
    Category.network.value: "Network Support",
    Category.software.value: "Software Support",
    Category.security.value: "Security Support",
    Category.access_management.value: "Access Management",
    Category.email.value: "Software Support",  # Email/Exchange application support
    Category.other.value: "Tier 1 Service Desk",
}

# Standard human-readable category labels
CATEGORY_DISPLAY_LABELS: Dict[str, str] = {
    Category.hardware.value: "Hardware",
    Category.network.value: "Network",
    Category.software.value: "Software",
    Category.access_management.value: "Access Management",
    Category.email.value: "Email",
    Category.security.value: "Security",
    Category.other.value: "Other",
}

# Normalization mapping for LLM output strings (case-insensitive & alias tolerant)
CATEGORY_NORMALIZATION_MAP: Dict[str, str] = {
    "hardware": Category.hardware.value,
    "network": Category.network.value,
    "software": Category.software.value,
    "access management": Category.access_management.value,
    "access_management": Category.access_management.value,
    "access": Category.access_management.value,
    "iam": Category.access_management.value,
    "identity": Category.access_management.value,
    "email": Category.email.value,
    "mail": Category.email.value,
    "outlook": Category.email.value,
    "security": Category.security.value,
    "infosec": Category.security.value,
    "cyber": Category.security.value,
    "other": Category.other.value,
    "general": Category.other.value,
}

LEVEL_NORMALIZATION_MAP: Dict[str, str] = {
    "high": "high",
    "p1": "high",
    "critical": "high",
    "medium": "medium",
    "p2": "medium",
    "p3": "medium",
    "moderate": "medium",
    "low": "low",
    "p4": "low",
    "minor": "low",
}


def normalize_category(raw_category: Optional[str]) -> str:
    """Safely normalizes raw string from LLM to a valid Category enum value."""
    if not raw_category:
        return Category.other.value
    cleaned = raw_category.strip().lower()
    return CATEGORY_NORMALIZATION_MAP.get(cleaned, Category.other.value)


def normalize_level(raw_level: Optional[str], default: str = "medium") -> str:
    """Safely normalizes raw impact/urgency string from LLM to 'high', 'medium', or 'low'."""
    if not raw_level:
        return default
    cleaned = raw_level.strip().lower()
    return LEVEL_NORMALIZATION_MAP.get(cleaned, default)


def resolve_assignment_group(category: str, raw_group: Optional[str] = None) -> str:
    """
    Recommends assignment group based on incident category.
    Allows valid predefined groups or falls back deterministically.
    """
    canonical_groups = {
        "Hardware Support",
        "Network Support",
        "Software Support",
        "Security Support",
        "Access Management",
        "Tier 1 Service Desk",
    }
    if raw_group:
        cleaned_g = raw_group.strip()
        for cg in canonical_groups:
            if cg.lower() == cleaned_g.lower():
                return cg
    return CATEGORY_ASSIGNMENT_MAP.get(category, "Tier 1 Service Desk")


def evaluate_priority_matrix(impact: str, urgency: str) -> Tuple[str, str, str]:
    """
    Evaluates final priority deterministically via the ITIL priority matrix.
    Returns:
        (priority_key, priority_code, priority_label)
        e.g. ('high', 'P2', 'P2 High')
    """
    norm_impact = normalize_level(impact, default="medium")
    norm_urgency = normalize_level(urgency, default="medium")
    priority_key = calculate_priority(norm_impact, norm_urgency)
    priority_label = PRIORITY_LABELS.get(priority_key, "P3 Medium")
    priority_code = priority_label.split()[0]  # 'P1', 'P2', 'P3', 'P4'
    return priority_key, priority_code, priority_label
