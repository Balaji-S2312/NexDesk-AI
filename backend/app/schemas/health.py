from typing import Optional
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = Field(..., examples=["healthy"])
    app_name: str = Field(..., examples=["NexDesk AI"])
    version: str = Field(..., examples=["0.1.0"])
    environment: str = Field(..., examples=["development"])
    database: Optional[str] = Field("healthy", examples=["healthy"])
    vector_store: Optional[str] = Field("healthy", examples=["healthy"])
    timestamp: str = Field(..., examples=["2026-11-12T11:40:00Z"])
