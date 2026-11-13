from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    filename: Optional[str] = None
    file_type: str
    file_size: int
    file_hash: Optional[str] = None
    category: str
    status: str
    error_message: Optional[str] = None
    page_count: int
    chunk_count: int
    created_by_id: Optional[int] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentDetailOut(DocumentOut):
    content_preview: str = ""


class DocumentListOut(BaseModel):
    items: List[DocumentOut]
    total: int


class DocumentDeleteResponse(BaseModel):
    id: int
    filename: Optional[str] = None
    deleted_chunks: int
    message: str


class SemanticSearchResult(BaseModel):
    chunk_id: str
    document_id: int
    source_filename: str
    title: str
    category: str
    page_number: int
    chunk_index: int
    text: str
    score: float = Field(..., description="Cosine similarity score between 0 and 1")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SemanticSearchResponse(BaseModel):
    query: str
    total: int
    results: List[SemanticSearchResult]
