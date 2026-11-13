from datetime import datetime, timezone
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.user import (
    OTPDispatchResponse,
    ResendVerificationRequest,
    SendOTPRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    VerificationStatusResponse,
    VerifyEmailRequest,
    VerifyOTPRequest,
)
from app.core.security import get_password_hash, verify_password, create_access_token
from app.api.deps import get_current_user, get_optional_current_user, require_admin
from app.services.notifications.email_service import (
    describe_delivery_status,
    is_https_provider_configured,
)
from app.services.verification_service import (
    OTP_EXPIRE_MINUTES,
    RESEND_COOLDOWN_SECONDS,
    issue_and_send_verification,
    request_verification_otp,
    verify_email_otp,
    verify_email_token,
    resend_verification_email as process_resend_verification,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new employee user account.
    Role escalation is strictly prevented: all registrations are assigned the 'employee' role.
    Generates a secure 6-digit OTP + backup activation token and dispatches an email.
    """
    normalized_email = user_in.email.strip().lower()
    
    # Check if email is already registered
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )
    
    # Enforce safe role: employee only; unverified initially
    new_user = User(
        name=user_in.name.strip(),
        email=normalized_email,
        password_hash=get_password_hash(user_in.password),
        role="employee",
        email_verified=False,
    )
    
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )
    db.refresh(new_user)

    # Generate 6-digit OTP & backup verification link, then dispatch email
    delivery_status_label: Optional[str] = None
    delivery_error_msg: Optional[str] = None
    try:
        delivery_log = issue_and_send_verification(db, new_user)
        delivery_status_label, delivery_error_msg = describe_delivery_status(delivery_log)
    except Exception as exc:
        delivery_status_label = "failed"
        delivery_error_msg = "Unable to queue verification email."
        logger.error("Failed to dispatch registration verification email for user_id=%s: %s", new_user.id, exc)

    user_out = UserResponse.model_validate(new_user)
    user_out.verification_delivery_status = delivery_status_label
    user_out.verification_delivery_error = delivery_error_msg
    return user_out


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user with email and password, issuing a signed JWT access token.
    """
    normalized_email = credentials.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate signed JWT
    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        email=user.email,
        name=user.name
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve the authenticated user's profile details.
    """
    return current_user


@router.post("/send-otp", response_model=OTPDispatchResponse, status_code=status.HTTP_200_OK)
def send_verification_otp_endpoint(
    payload: Optional[SendOTPRequest] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Issue a new 6-digit verification OTP email (10-minute expiration, 60-second cooldown).
    Uses the authenticated user when signed in, or falls back to payload email safely without enumeration.
    """
    email = payload.email if payload else None
    if current_user is None and not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registered email address is required.",
        )

    dispatched = request_verification_otp(db, current_user=current_user, email=email)
    if current_user is not None and not dispatched:
        return OTPDispatchResponse(
            message="Your email address is already verified.",
            cooldown_seconds=0,
            expires_in_seconds=0,
            already_verified=True,
            delivery_stage="already_verified",
        )

    stage = (
        ("accepted_by_provider" if is_https_provider_configured() else "accepted_by_smtp")
        if current_user is not None
        else "request_accepted"
    )
    msg = (
        "Verification code accepted by mail server for dispatch. Check Inbox or Spam."
        if current_user is not None
        else "If this email is registered and unverified, a 6-digit verification code has been accepted for dispatch."
    )
    return OTPDispatchResponse(
        message=msg,
        cooldown_seconds=RESEND_COOLDOWN_SECONDS,
        expires_in_seconds=OTP_EXPIRE_MINUTES * 60,
        already_verified=False,
        delivery_stage=stage,
    )


@router.post("/verify-otp", response_model=UserResponse)
def verify_otp_endpoint(
    payload: VerifyOTPRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Verify an employee email address using a cryptographically hashed single-use 6-digit OTP.
    """
    return verify_email_otp(
        db,
        otp=payload.otp,
        current_user=current_user,
        email=payload.email,
    )


@router.post("/verify-email", response_model=UserResponse)
def verify_email_endpoint(
    payload: Optional[VerifyEmailRequest] = None,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Verify employee email using single-use cryptographic link token.
    Accepts token via JSON payload or query parameter.
    """
    resolved_token = None
    if payload and payload.token:
        resolved_token = payload.token.strip()
    elif token:
        resolved_token = token.strip()

    if resolved_token:
        verified_user = verify_email_token(db, resolved_token)
        return verified_user

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Verification token is required.",
    )


@router.post("/resend-verification", response_model=OTPDispatchResponse, status_code=status.HTTP_200_OK)
def resend_verification_endpoint(
    payload: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    Resend 6-digit OTP and verification link to registered employee address with rate limiting.
    """
    process_resend_verification(db, payload.email)
    return OTPDispatchResponse(
        message="If this email is registered and unverified, a 6-digit verification code has been accepted for dispatch.",
        cooldown_seconds=RESEND_COOLDOWN_SECONDS,
        expires_in_seconds=OTP_EXPIRE_MINUTES * 60,
        already_verified=False,
        delivery_stage="request_accepted",
    )


@router.get("/verification-status", response_model=VerificationStatusResponse)
def check_verification_status(
    current_user: User = Depends(get_current_user),
):
    """
    Check the current authenticated user's email verification status.
    """
    return VerificationStatusResponse(
        email_verified=bool(current_user.email_verified),
        email=current_user.email,
        email_verified_at=current_user.email_verified_at,
    )


@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Administrative endpoint: List all users in the organization.
    Protected strictly by role: only users with the 'admin' role can access.
    """
    users = db.query(User).order_by(User.id).all()
    return users
