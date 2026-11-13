from datetime import datetime, timezone
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.user import (
    ConfirmEmailRequest,
    ConfirmEmailResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.core.security import get_password_hash, verify_password, create_access_token
from app.api.deps import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new employee user account.
    Role escalation is strictly prevented: all registrations are assigned the 'employee' role
    and start with email confirmation status set to False (Unconfirmed).
    """
    normalized_email = user_in.email.strip().lower()

    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

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
    return new_user


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: UserLoginRequest,
    db: Session = Depends(get_db),
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

    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        email=user.email,
        name=user.name,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user,
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the authenticated user's profile details.
    """
    return current_user


@router.post("/confirm-email", response_model=ConfirmEmailResponse, status_code=status.HTTP_200_OK)
def confirm_own_email(
    payload: ConfirmEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    In-app self-confirmation of the authenticated user's own registered email address.
    Compares trimmed, case-normalized email strictly against current_user.email on the server.
    This sets user-confirmed status only and is not proof of external mailbox ownership.
    """
    submitted_email = (payload.email or "").strip().lower()
    registered_email = (current_user.email or "").strip().lower()

    if not submitted_email or submitted_email != registered_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email addresses do not match. Please check and try again.",
        )

    if not current_user.email_verified:
        current_user.email_verified = True
        current_user.email_verified_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(current_user)
    elif current_user.email_verified_at is None:
        current_user.email_verified_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(current_user)

    return ConfirmEmailResponse(
        message="Email address confirmed successfully.",
        user=current_user,
    )


@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Administrative endpoint: List all users in the organization.
    Protected strictly by role: only users with the 'admin' role can access.
    """
    users = db.query(User).order_by(User.id).all()
    return users
