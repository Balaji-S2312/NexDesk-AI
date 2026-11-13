"""Pure ITSM business rules: enums, impact/urgency priority matrix and SLA targets."""
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Tuple


class Category(str, Enum):
    hardware = "hardware"
    software = "software"
    network = "network"
    access_management = "access_management"
    email = "email"
    security = "security"
    other = "other"


class Impact(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Urgency(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Priority(str, Enum):
    critical = "critical"  # P1
    high = "high"          # P2
    medium = "medium"      # P3
    low = "low"            # P4


class Status(str, Enum):
    open = "open"
    assigned = "assigned"
    in_progress = "in_progress"
    pending = "pending"
    resolved = "resolved"
    closed = "closed"


PRIORITY_LABELS: Dict[str, str] = {
    "critical": "P1 Critical",
    "high": "P2 High",
    "medium": "P3 Medium",
    "low": "P4 Low",
}

# Standard ITIL impact x urgency matrix.
PRIORITY_MATRIX: Dict[Tuple[str, str], str] = {
    ("high", "high"): "critical",
    ("high", "medium"): "high",
    ("high", "low"): "medium",
    ("medium", "high"): "high",
    ("medium", "medium"): "medium",
    ("medium", "low"): "low",
    ("low", "high"): "medium",
    ("low", "medium"): "low",
    ("low", "low"): "low",
}

# Fallback resolution targets (hours) if no SLAPolicy row exists for a priority.
DEFAULT_RESOLUTION_HOURS: Dict[str, int] = {"critical": 4, "high": 8, "medium": 24, "low": 48}

# Fallback response targets (minutes) if no SLAPolicy row exists for a priority.
DEFAULT_RESPONSE_MINUTES: Dict[str, int] = {"critical": 15, "high": 30, "medium": 240, "low": 480}

OPEN_STATUSES = ("open", "assigned", "in_progress", "pending")
DONE_STATUSES = ("resolved", "closed")


def calculate_priority(impact: str, urgency: str) -> str:
    return PRIORITY_MATRIX[(impact, urgency)]


def calculate_sla_deadline(created_at: datetime, resolution_hours: int) -> datetime:
    return created_at + timedelta(hours=resolution_hours)
