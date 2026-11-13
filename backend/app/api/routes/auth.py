from datetime import datetime, timezone
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.user import (
    ResendVerificationRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    VerificationStatusResponse,
    VerifyEmailRequest,
)
from app.core.security import get_password_hash, verify_password, create_access_token
from app.api.deps import get_current_user, require_admin
from app.services.verification_service import (
    create_verification_token,
    send_verification_email,
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
    Generates a secure verification token and dispatches an activation email.
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
    db.commit()
    db.refresh(new_user)

    # Generate token & dispatch email verification link
    try:
        raw_token = create_verification_token(db, new_user)
        send_verification_email(db, new_user, raw_token)
    except Exception as exc:
        logger.error("Failed to dispatch registration verification email: %s", exc)

    return new_user


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


@router.post("/verify-email", response_model=UserResponse)
def verify_email_endpoint(
    payload: Optional[VerifyEmailRequest] = None,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(lambda: None),
):
    """
    Verify employee email using single-use cryptographic token.
    Accepts token via JSON payload or query parameter, or falls back to current authenticated user.
    """
    resolved_token = None
    if payload and payload.token:
        resolved_token = payload.token.strip()
    elif token:
        resolved_token = token.strip()

    if resolved_token:
        verified_user = verify_email_token(db, resolved_token)
        return verified_user

    # Fallback: if caller passed Bearer token without query token
    # (used for backward compatibility in internal session verification)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Verification token is required.",
    )


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
def resend_verification_endpoint(
    payload: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    Resend verification email to registered employee address with rate limiting.
    """
    process_resend_verification(db, payload.email)
    return {"message": "Verification link has been sent if the email is registered."}


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
