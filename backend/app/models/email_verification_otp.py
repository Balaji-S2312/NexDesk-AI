"""Email Verification OTP model for cryptographically hashed, single-use 6-digit OTP codes."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database.session import Base


class EmailVerificationOTP(Base):
    __tablename__ = "email_verification_otps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    otp_hash = Column(String(64), nullable=False, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    invalidated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<EmailVerificationOTP id={self.id} user_id={self.user_id} "
            f"attempts={self.attempt_count} used={self.used_at is not None}>"
        )
