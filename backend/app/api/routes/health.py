import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.schemas.health import HealthResponse
from app.core.config import settings
from app.database.session import get_db

router = APIRouter()

@router.get("/health", response_model=HealthResponse, tags=["System Health"])
def get_health(db: Session = Depends(get_db)):
    """
    Returns the system health status, version, and core subsystem connectivity.
    Does NOT leak secrets, database connection strings, or internal infrastructure details.
    """
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    chroma_status = "healthy"
    try:
        if not os.path.exists(settings.CHROMA_PERSIST_DIRECTORY):
            chroma_status = "initialized_pending_write"
    except Exception:
        chroma_status = "unavailable"

    overall_status = "healthy" if db_status == "healthy" else "degraded"

    return HealthResponse(
        status=overall_status,
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database=db_status,
        vector_store=chroma_status,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
