from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Float, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base

class SLAPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    priority = Column(String(50), nullable=False, index=True)
    response_time_minutes = Column(Integer, nullable=False, default=240)
    response_time_hours = Column(Float, nullable=False, default=4.0)
    resolution_time_hours = Column(Integer, nullable=False, default=24)
    business_hours_only = Column(Boolean, nullable=False, default=False)
    escalation_contact = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    tickets = relationship("Ticket", back_populates="sla_policy")

    def __repr__(self) -> str:
        return f"<SLAPolicy id={self.id} name='{self.name}' priority='{self.priority}' resp_mins={self.response_time_minutes} res_hrs={self.resolution_time_hours}>"
