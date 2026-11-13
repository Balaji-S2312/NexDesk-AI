"""
Email verification token generation, single-use validation, rate limiting, and delivery service.
Module 12B compliant.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_verification import EmailVerificationToken
from app.models.user import User
from app.services.email_templates import render_email_verification
from app.services.notifications.email_service import is_valid_email, send_email

logger = logging.getLogger(__name__)

RESEND_COOLDOWN_SECONDS = 60


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _hash_token(token: str) -> str:
    """Computes SHA-256 digest of plaintext verification token."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


hash_token = _hash_token


def create_verification_token(db: Session, user: User) -> str:
    """
    Generates a cryptographically secure random token, stores its SHA-256 hash
    with an expiration time (default 30 mins), and returns the raw token.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = _utc_now() + timedelta(minutes=int(settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES))

    # Invalidate any prior unused tokens for this user
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.used_at.is_(None),
    ).update({"used_at": _utc_now()}, synchronize_session=False)

    record = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_at=_utc_now(),
    )
    db.add(record)
    db.commit()

    return raw_token


def send_verification_email(db: Session, user: User, raw_token: str) -> None:
    """Renders HTML template and dispatches email verification message."""
    base_url = (settings.FRONTEND_URL or settings.FRONTEND_BASE_URL or "http://localhost:5173").rstrip("/")
    verification_url = f"{base_url}/verify-email?token={raw_token}"

    template = render_email_verification(
        user_name=user.name,
        verification_url=verification_url,
        expires_minutes=int(settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES),
    )

    send_email(
        db,
        recipient_email=user.email,
        subject=template["subject"],
        html_body=template["html_body"],
        text_body=template["text_body"],
        event_type="email_verification",
        event_key=f"verify_{user.id}_{_hash_token(raw_token)[:16]}",
        recipient_user_id=user.id,
        recipient_verified=False,
    )


def verify_email_token(db: Session, raw_token: str) -> User:
    """
    Validates token hash, checks expiration and single-use status,
    marks employee email verified, and invalidates the token.
    """
    cleaned = raw_token.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token cannot be empty.",
        )

    token_hash = _hash_token(cleaned)
    now = _utc_now()

    record = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.token_hash == token_hash)
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is invalid or has already been used.",
        )

    if record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification token has already been used.",
        )

    if _as_utc(record.expires_at) < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification token has expired. Please request a new verification link.",
        )

    # Invalidate token
    record.used_at = now

    # Mark user email verified
    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User associated with verification token not found.",
        )

    user.email_verified = True
    user.email_verified_at = now
    db.commit()
    db.refresh(user)

    logger.info("Successfully verified email for user %s (%s)", user.id, user.email)
    return user


def resend_verification_email(db: Session, email: str) -> bool:
    """
    Checks user existence, applies 60-second rate-limiting cooldown,
    generates new token and dispatches email.
    Safely prevents user enumeration by reporting success even if email not registered.
    """
    normalized = email.strip().lower()
    if not is_valid_email(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please provide a valid corporate email address.",
        )

    user = db.query(User).filter(User.email == normalized).first()
    if not user:
        # Do not reveal whether arbitrary email addresses are registered (Security requirement)
        return True

    if user.email_verified:
        return True

    # Rate limiting: check most recent token created for user
    last_token = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )

    if last_token:
        # Compare in UTC
        created = last_token.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed = (_utc_now() - created).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            remaining = int(RESEND_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} seconds before requesting another verification email.",
            )

    token = create_verification_token(db, user)
    send_verification_email(db, user, token)
    return True
