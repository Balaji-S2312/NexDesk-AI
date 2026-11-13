from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base

class AssignmentGroup(Base):
    __tablename__ = "assignment_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    tickets = relationship("Ticket", back_populates="group")

    def __repr__(self) -> str:
        return f"<AssignmentGroup id={self.id} name='{self.name}'>"
