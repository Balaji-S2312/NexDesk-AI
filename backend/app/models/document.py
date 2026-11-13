from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=True, index=True)
    content = Column(Text, nullable=False, default="")
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(50), nullable=False, default="runbook")
    file_size = Column(Integer, nullable=False, default=0)
    file_hash = Column(String(64), nullable=True, index=True)
    category = Column(String(100), nullable=False, default="general", index=True)
    status = Column(String(50), nullable=False, default="completed", index=True)
    error_message = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=False, default=1)
    chunk_count = Column(Integer, nullable=False, default=0)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    creator = relationship("User", back_populates="documents")

    def __repr__(self) -> str:
        return f"<Document id={self.id} title='{self.title[:30]}' status='{self.status}'>"
