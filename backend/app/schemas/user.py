from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, examples=["John Doe"])
    email: EmailStr = Field(..., examples=["john.doe@nexdesk.ai"])

class UserRegisterRequest(UserBase):
    password: str = Field(..., min_length=8, max_length=128, description="Password must be at least 8 characters long")
    # Note: Role is intentionally not accepted from clients during registration to prevent unauthorized role escalation.

class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["john.doe@nexdesk.ai"])
    password: str = Field(..., min_length=1, max_length=128)

class UserResponse(UserBase):
    id: int
    role: str
    email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    created_at: datetime
    verification_delivery_status: Optional[str] = None
    verification_delivery_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class VerifyEmailRequest(BaseModel):
    token: Optional[str] = None


class SendOTPRequest(BaseModel):
    email: Optional[EmailStr] = None


class VerifyOTPRequest(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    email: Optional[EmailStr] = None


class OTPDispatchResponse(BaseModel):
    message: str
    cooldown_seconds: int = 60
    expires_in_seconds: int = 600
    already_verified: bool = False
    delivery_stage: str = "accepted_by_smtp"


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class VerificationStatusResponse(BaseModel):
    email_verified: bool
    email: str
    email_verified_at: Optional[datetime] = None
