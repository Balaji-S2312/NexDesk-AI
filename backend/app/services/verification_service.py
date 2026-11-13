"""
Email verification OTP and token generation, single-use validation, rate limiting, and delivery service.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import re
import secrets
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_verification import EmailVerificationToken
from app.models.email_verification_otp import EmailVerificationOTP
from app.models.notification import EmailDeliveryLog
from app.models.user import User
from app.services.email_templates import render_email_verification
from app.services.notifications.email_service import is_valid_email, send_email

logger = logging.getLogger(__name__)

RESEND_COOLDOWN_SECONDS = int(settings.EMAIL_VERIFICATION_OTP_COOLDOWN_SECONDS)
OTP_EXPIRE_MINUTES = int(settings.EMAIL_VERIFICATION_OTP_EXPIRE_MINUTES)
OTP_MAX_ATTEMPTS = int(settings.EMAIL_VERIFICATION_OTP_MAX_ATTEMPTS)
OTP_RATE_WINDOW_MINUTES = int(settings.EMAIL_VERIFICATION_OTP_RATE_WINDOW_MINUTES)
OTP_MAX_PER_WINDOW = int(settings.EMAIL_VERIFICATION_OTP_MAX_PER_WINDOW)
_SIX_DIGIT_RE = re.compile(r"^\d{6}$")


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


def hash_otp(user_id: int, otp: str) -> str:
    """Computes keyed SHA-256 digest of a 6-digit OTP bound to user_id and JWT_SECRET."""
    material = f"{settings.JWT_SECRET}:{int(user_id)}:{otp.strip()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def generate_numeric_otp() -> str:
    """Generates a cryptographically random 6-digit numeric OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def create_verification_token(db: Session, user: User) -> str:
    """
    Generates a cryptographically secure random link token, stores its SHA-256 hash
    with an expiration time, and invalidates prior unused tokens for this user.
    """
    now = _utc_now()
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = now + timedelta(minutes=int(settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES))

    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)

    record = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(record)
    db.commit()

    return raw_token


def create_verification_otp(db: Session, user: User) -> str:
    """
    Generates a cryptographically secure 6-digit OTP, stores only its keyed hash
    with a 10-minute expiration, and invalidates any previously issued active OTPs.
    """
    now = _utc_now()
    otp_code = generate_numeric_otp()
    otp_digest = hash_otp(user.id, otp_code)
    expires_at = now + timedelta(minutes=OTP_EXPIRE_MINUTES)

    # Invalidate previously issued unused/un-invalidated OTPs for this account
    db.query(EmailVerificationOTP).filter(
        EmailVerificationOTP.user_id == user.id,
        EmailVerificationOTP.used_at.is_(None),
        EmailVerificationOTP.invalidated_at.is_(None),
    ).update({"invalidated_at": now}, synchronize_session=False)

    otp_record = EmailVerificationOTP(
        user_id=user.id,
        otp_hash=otp_digest,
        attempt_count=0,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(otp_record)
    db.commit()

    return otp_code


def send_verification_email(
    db: Session,
    user: User,
    raw_token: str,
    otp_code: Optional[str] = None,
) -> EmailDeliveryLog:
    """Renders verification email (6-digit OTP + backup link) and dispatches via SMTP."""
    base_url = (settings.FRONTEND_URL or settings.FRONTEND_BASE_URL or "http://localhost:5173").rstrip("/")
    verification_url = f"{base_url}/verify-email?token={raw_token}"

    template = render_email_verification(
        user_name=user.name,
        verification_url=verification_url,
        expires_minutes=int(settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES),
        otp_code=otp_code,
        user_email=user.email,
        otp_expires_minutes=OTP_EXPIRE_MINUTES,
    )

    event_suffix = _hash_token(raw_token)[:16]
    return send_email(
        db,
        recipient_email=user.email,
        subject=template["subject"],
        html_body=template["html_body"],
        text_body=template["text_body"],
        event_type="email_verification",
        event_key=f"verify_{user.id}_{event_suffix}",
        recipient_user_id=user.id,
        recipient_verified=False,
    )


def issue_and_send_verification(db: Session, user: User) -> EmailDeliveryLog:
    """Issues a fresh 6-digit OTP + backup verification token and sends the verification email."""
    raw_token = create_verification_token(db, user)
    otp_code = create_verification_otp(db, user)
    return send_verification_email(db, user, raw_token, otp_code=otp_code)


def _mark_user_verified(db: Session, user: User, now: datetime) -> None:
    """Marks the user account email_verified=True and invalidates remaining open OTPs/tokens."""
    db.query(EmailVerificationOTP).filter(
        EmailVerificationOTP.user_id == user.id,
        EmailVerificationOTP.used_at.is_(None),
        EmailVerificationOTP.invalidated_at.is_(None),
    ).update({"invalidated_at": now}, synchronize_session=False)

    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)

    user.email_verified = True
    user.email_verified_at = now
    db.commit()
    db.refresh(user)


def verify_email_token(db: Session, raw_token: str) -> User:
    """
    Validates link token hash, checks expiration and single-use status,
    marks employee email verified, and invalidates the token and open OTPs.
    """
    cleaned = (raw_token or "").strip()
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
            detail="This verification token has expired. Please request a new verification code.",
        )

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User associated with verification token not found.",
        )

    record.used_at = now
    _mark_user_verified(db, user, now)

    logger.info("Successfully verified email via token for user_id=%s", user.id)
    return user


def verify_email_otp(
    db: Session,
    *,
    otp: str,
    current_user: Optional[User] = None,
    email: Optional[str] = None,
) -> User:
    """
    Validates a 6-digit OTP against hashed storage, expiration (10 mins), attempt limits,
    and single-use guarantees without logging plaintext OTP values.
    """
    cleaned_otp = (otp or "").strip()
    if not _SIX_DIGIT_RE.match(cleaned_otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a valid 6-digit numeric verification code.",
        )

    target_user: Optional[User] = current_user
    if target_user is not None:
        if email and email.strip().lower() != target_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Submitted email does not match the signed-in account.",
            )
    else:
        normalized_email = (email or "").strip().lower()
        if not is_valid_email(normalized_email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code.",
            )
        target_user = db.query(User).filter(User.email == normalized_email).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code.",
            )

    now = _utc_now()
    submitted_hash = hash_otp(target_user.id, cleaned_otp)

    # Reject reuse of a previously verified OTP explicitly
    reused_record = (
        db.query(EmailVerificationOTP)
        .filter(
            EmailVerificationOTP.user_id == target_user.id,
            EmailVerificationOTP.otp_hash == submitted_hash,
            EmailVerificationOTP.used_at.is_not(None),
        )
        .order_by(EmailVerificationOTP.created_at.desc())
        .first()
    )
    if reused_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification code has already been used. Please request a new code.",
        )

    active_otp = (
        db.query(EmailVerificationOTP)
        .filter(
            EmailVerificationOTP.user_id == target_user.id,
            EmailVerificationOTP.used_at.is_(None),
            EmailVerificationOTP.invalidated_at.is_(None),
        )
        .order_by(EmailVerificationOTP.created_at.desc())
        .first()
    )

    if not active_otp:
        latest_any = (
            db.query(EmailVerificationOTP)
            .filter(EmailVerificationOTP.user_id == target_user.id)
            .order_by(EmailVerificationOTP.created_at.desc())
            .first()
        )
        if latest_any and latest_any.used_at is None and _as_utc(latest_any.expires_at) < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This verification code has expired. Please request a new code.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active verification code found. Please request a new code.",
        )

    if _as_utc(active_otp.expires_at) < now:
        active_otp.invalidated_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification code has expired. Please request a new code.",
        )

    if active_otp.attempt_count >= OTP_MAX_ATTEMPTS:
        active_otp.invalidated_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed verification attempts. Please request a new code.",
        )

    if not secrets.compare_digest(active_otp.otp_hash, submitted_hash):
        active_otp.attempt_count += 1
        if active_otp.attempt_count >= OTP_MAX_ATTEMPTS:
            active_otp.invalidated_at = now
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed verification attempts. Please request a new code.",
            )
        remaining = OTP_MAX_ATTEMPTS - active_otp.attempt_count
        db.commit()
        detail = (
            f"Invalid verification code. {remaining} attempt(s) remaining."
            if current_user is not None
            else "Invalid or expired verification code."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    active_otp.used_at = now
    active_otp.invalidated_at = now
    _mark_user_verified(db, target_user, now)

    logger.info("Successfully verified email via OTP for user_id=%s", target_user.id)
    return target_user


def _enforce_otp_rate_limits(db: Session, user: User) -> None:
    """Enforces 60-second resend cooldown and sliding 15-minute request rate limit."""
    now = _utc_now()

    latest_otp = (
        db.query(EmailVerificationOTP)
        .filter(EmailVerificationOTP.user_id == user.id)
        .order_by(EmailVerificationOTP.created_at.desc())
        .first()
    )
    latest_token = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )

    timestamps = [
        _as_utc(rec.created_at)
        for rec in (latest_otp, latest_token)
        if rec is not None and rec.created_at is not None
    ]
    if timestamps:
        most_recent = max(timestamps)
        elapsed = (now - most_recent).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            remaining = max(1, int(RESEND_COOLDOWN_SECONDS - elapsed))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} seconds before requesting another verification code.",
            )

    window_start = now - timedelta(minutes=OTP_RATE_WINDOW_MINUTES)
    recent_count = (
        db.query(EmailVerificationOTP)
        .filter(
            EmailVerificationOTP.user_id == user.id,
            EmailVerificationOTP.created_at >= window_start,
        )
        .count()
    )
    if recent_count >= OTP_MAX_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit reached for verification requests. Please wait a few minutes and try again.",
        )


def request_verification_otp(
    db: Session,
    *,
    current_user: Optional[User] = None,
    email: Optional[str] = None,
) -> bool:
    """
    Requests a fresh 6-digit OTP email (with backup verification link) for an unverified user.
    Enforces cooldown + sliding rate limit and prevents unauthenticated account enumeration.
    """
    if current_user is not None:
        if current_user.email_verified:
            return False
        target_user = current_user
    else:
        normalized = (email or "").strip().lower()
        if not is_valid_email(normalized):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Please provide a valid corporate email address.",
            )
        target_user = db.query(User).filter(User.email == normalized).first()
        if not target_user or target_user.email_verified:
            # Never disclose whether an arbitrary email is registered or verified
            return True

    _enforce_otp_rate_limits(db, target_user)
    delivery_log = issue_and_send_verification(db, target_user)
    if delivery_log.delivery_status == "failed":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to send verification email right now. Please try again shortly.",
        )
    return True


def resend_verification_email(db: Session, email: str) -> bool:
    """Backward-compatible wrapper dispatching 6-digit OTP + verification link with rate limiting."""
    return request_verification_otp(db, current_user=None, email=email)
