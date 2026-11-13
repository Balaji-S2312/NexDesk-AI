from datetime import datetime, timezone
import logging
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.database.session import engine, Base, SessionLocal
from app.models import User, SLAPolicy, AssignmentGroup
from app.core.config import settings
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

# Columns added to `tickets` in Module 4 & 10. (name, DDL type/default)
_TICKET_MIGRATIONS = [
    ("ticket_number", "VARCHAR(20)"),
    ("subcategory", "VARCHAR(100)"),
    ("impact", "VARCHAR(20) NOT NULL DEFAULT 'medium'"),
    ("urgency", "VARCHAR(20) NOT NULL DEFAULT 'medium'"),
    ("response_deadline", "DATETIME"),
    ("sla_deadline", "DATETIME"),
    ("first_responded_at", "DATETIME"),
    ("resolution_notes", "TEXT"),
    ("resolved_at", "DATETIME"),
]

_LEGACY_CATEGORY_MAP = {"access": "access_management", "general": "other"}


def migrate_tickets_table() -> None:
    """Idempotently upgrade a pre-Module-4 `tickets` table in place (SQLite ALTER TABLE)."""
    insp = inspect(engine)
    if "tickets" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("tickets")}
    with engine.begin() as conn:
        for name, ddl in _TICKET_MIGRATIONS:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE tickets ADD COLUMN {name} {ddl}"))
                logger.info("Migrated tickets table: added column %s", name)
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_tickets_ticket_number ON tickets (ticket_number)"))
        # Backfill ticket numbers and normalise legacy categories.
        conn.execute(text(
            "UPDATE tickets SET ticket_number = 'INC' || substr('0000000' || id, -7, 7) "
            "WHERE ticket_number IS NULL"
        ))
        for old, new in _LEGACY_CATEGORY_MAP.items():
            conn.execute(text("UPDATE tickets SET category = :new WHERE category = :old"),
                         {"new": new, "old": old})
        # Backfill SLA deadline from created_at + policy hours for legacy rows.
        conn.execute(text(
            "UPDATE tickets SET sla_deadline = datetime(created_at, '+' || COALESCE("
            "(SELECT resolution_time_hours FROM sla_policies s WHERE s.priority = tickets.priority), 24"
            ") || ' hours') WHERE sla_deadline IS NULL"
        ))


# Columns added to `documents` in Module 6.
_DOCUMENT_MIGRATIONS = [
    ("filename", "VARCHAR(255)"),
    ("file_size", "INTEGER NOT NULL DEFAULT 0"),
    ("file_hash", "VARCHAR(64)"),
    ("status", "VARCHAR(50) NOT NULL DEFAULT 'completed'"),
    ("error_message", "TEXT"),
    ("page_count", "INTEGER NOT NULL DEFAULT 1"),
    ("chunk_count", "INTEGER NOT NULL DEFAULT 0"),
]


def migrate_documents_table() -> None:
    """Idempotently upgrade a pre-Module-6 `documents` table in place (SQLite ALTER TABLE)."""
    insp = inspect(engine)
    if "documents" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("documents")}
    with engine.begin() as conn:
        for name, ddl in _DOCUMENT_MIGRATIONS:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE documents ADD COLUMN {name} {ddl}"))
                logger.info("Migrated documents table: added column %s", name)
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_file_hash ON documents (file_hash)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_filename ON documents (filename)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_status ON documents (status)"))


def migrate_users_table() -> None:
    """Idempotently add Module 9A email verification columns to `users` in place."""
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("users")}
    with engine.begin() as conn:
        if "email_verified" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0"))
            logger.info("Migrated users table: added column email_verified")
        if "email_verified_at" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified_at DATETIME"))
            logger.info("Migrated users table: added column email_verified_at")


def migrate_sla_policies_table() -> None:
    """Idempotently add Module 10 SLA columns to `sla_policies` in place."""
    insp = inspect(engine)
    if "sla_policies" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("sla_policies")}
    with engine.begin() as conn:
        if "response_time_minutes" not in existing:
            conn.execute(text("ALTER TABLE sla_policies ADD COLUMN response_time_minutes INTEGER NOT NULL DEFAULT 240"))
            logger.info("Migrated sla_policies table: added column response_time_minutes")
        if "business_hours_only" not in existing:
            conn.execute(text("ALTER TABLE sla_policies ADD COLUMN business_hours_only BOOLEAN NOT NULL DEFAULT 0"))
            logger.info("Migrated sla_policies table: added column business_hours_only")
        if "escalation_contact" not in existing:
            conn.execute(text("ALTER TABLE sla_policies ADD COLUMN escalation_contact VARCHAR(255)"))
            logger.info("Migrated sla_policies table: added column escalation_contact")


DEMO_ADMIN_EMAIL = "admin@nexdesk.ai"
DEMO_ADMIN_PASSWORD = "AdminPassword123!"

DEMO_EMPLOYEE_EMAIL = "employee@nexdesk.ai"
DEMO_EMPLOYEE_PASSWORD = "EmployeePassword123!"

def init_db(db: Session = None) -> None:
    """
    Initializes the database:
    1. Creates all tables registered in Base.metadata (and runs SQLite in-place upgrades if on SQLite).
    2. Seeds initial admin and employee accounts if not already present (respecting production env).
    3. Seeds default SLA policies and assignment groups.
    """
    # 1. Create tables
    Base.metadata.create_all(bind=engine)
    if db is None and engine.dialect.name == "sqlite":
        migrate_users_table()
        migrate_tickets_table()
        migrate_documents_table()
        migrate_sla_policies_table()
    
    close_after = False
    if db is None:
        db = SessionLocal()
        close_after = True

    try:
        is_prod = settings.ENVIRONMENT.lower() == "production"
        # 2. Seed Admin User (env-configured first in production, or demo in non-prod)
        seed_admin_email = (settings.ADMIN_SEED_EMAIL or "").strip() or (
            DEMO_ADMIN_EMAIL if (not is_prod or settings.SEED_DEMO_ACCOUNTS) else ""
        )
        seed_admin_pwd = (settings.ADMIN_SEED_PASSWORD or "").strip() or (
            DEMO_ADMIN_PASSWORD if (not is_prod or settings.SEED_DEMO_ACCOUNTS) else ""
        )
        if seed_admin_email and seed_admin_pwd:
            admin_user = db.query(User).filter(User.email == seed_admin_email).first()
            if not admin_user:
                admin_user = User(
                    name="System Administrator",
                    email=seed_admin_email,
                    password_hash=get_password_hash(seed_admin_pwd),
                    role="admin",
                    email_verified=True,
                )
                db.add(admin_user)
                logger.info(f"Seeded administrator account: {seed_admin_email}")
            elif not admin_user.email_verified:
                admin_user.email_verified = True

        # Seed Demo Employee User (only in non-production or when SEED_DEMO_ACCOUNTS=True)
        if not is_prod or settings.SEED_DEMO_ACCOUNTS:
            emp_user = db.query(User).filter(User.email == DEMO_EMPLOYEE_EMAIL).first()
            if not emp_user:
                emp_user = User(
                    name="Demo Employee",
                    email=DEMO_EMPLOYEE_EMAIL,
                    password_hash=get_password_hash(DEMO_EMPLOYEE_PASSWORD),
                    role="employee",
                    email_verified=True,
                    email_verified_at=datetime.now(timezone.utc),
                )
                db.add(emp_user)
                logger.info(f"Seeded demo employee account: {DEMO_EMPLOYEE_EMAIL}")
            elif not emp_user.email_verified:
                emp_user.email_verified = True

        # 3. Seed Default SLA Policies (Module 10 configurable demo policies)
        # P1: Response 15m (0.25h), Resolution 4h, 24x7
        # P2: Response 30m (0.5h), Resolution 8h, 24x7
        # P3: Response 4h (240m), Resolution 24h, Business hours
        # P4: Response 8h (480m), Resolution 48h, Business hours
        default_slas = [
            {
                "name": "P1 - Critical Outage SLA",
                "priority": "critical",
                "response_time_minutes": 15,
                "response_time_hours": 0.25,
                "resolution_time_hours": 4,
                "business_hours_only": False,
                "escalation_contact": "pagerduty-ops@nexdesk.ai",
            },
            {
                "name": "P2 - Major Degradation SLA",
                "priority": "high",
                "response_time_minutes": 30,
                "response_time_hours": 0.5,
                "resolution_time_hours": 8,
                "business_hours_only": False,
                "escalation_contact": "tier2-leads@nexdesk.ai",
            },
            {
                "name": "P3 - Standard Request SLA",
                "priority": "medium",
                "response_time_minutes": 240,
                "response_time_hours": 4.0,
                "resolution_time_hours": 24,
                "business_hours_only": True,
                "escalation_contact": "servicedesk@nexdesk.ai",
            },
            {
                "name": "P4 - Minor Inquiry SLA",
                "priority": "low",
                "response_time_minutes": 480,
                "response_time_hours": 8.0,
                "resolution_time_hours": 48,
                "business_hours_only": True,
                "escalation_contact": "servicedesk@nexdesk.ai",
            },
        ]
        for sla in default_slas:
            existing = db.query(SLAPolicy).filter(SLAPolicy.priority == sla["priority"]).first()
            if not existing:
                db.add(SLAPolicy(**sla))
            else:
                # Update existing policies with Module 10 parameters
                existing.name = sla["name"]
                existing.response_time_minutes = sla["response_time_minutes"]
                existing.response_time_hours = sla["response_time_hours"]
                existing.resolution_time_hours = sla["resolution_time_hours"]
                existing.business_hours_only = sla["business_hours_only"]
                if sla["escalation_contact"] and not existing.escalation_contact:
                    existing.escalation_contact = sla["escalation_contact"]

        # 4. Seed Default Assignment Groups
        default_groups = [
            {"name": "Hardware Support", "description": "Laptops, workstations, peripherals, monitors, and device hardware."},
            {"name": "Network Support", "description": "LAN, Wi-Fi, WAN, VPN, routing, and network connectivity."},
            {"name": "Software Support", "description": "OS, client applications, productivity suites, and virtualized tools."},
            {"name": "Security Support", "description": "Security incident response, endpoint protection, and threat remediation."},
            {"name": "Access Management", "description": "SSO, IAM, Okta, password resets, and MFA hardware/software tokens."},
            {"name": "Tier 1 Service Desk", "description": "General frontline IT service desk support."},
        ]
        for group in default_groups:
            existing = db.query(AssignmentGroup).filter(AssignmentGroup.name == group["name"]).first()
            if not existing:
                db.add(AssignmentGroup(**group))

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        if close_after:
            db.close()
