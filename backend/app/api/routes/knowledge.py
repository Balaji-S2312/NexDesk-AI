from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_admin
from app.database.session import get_db
from app.models.document import Document
from app.models.user import User
from app.services.rag.extractor import DocumentExtractionError
from app.services.rag.pipeline import (
    DocumentTooLargeError,
    DocumentValidationError,
    DuplicateDocumentError,
    delete_document,
    ingest_document,
    reprocess_document,
    semantic_search,
    serialize_document,
)
from app.services.rag.schemas import (
    DocumentDeleteResponse,
    DocumentDetailOut,
    DocumentListOut,
    DocumentOut,
    SemanticSearchResponse,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base & RAG"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: str = Form("general"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Admin-only endpoint to upload PDF, DOCX, or TXT files into the RAG pipeline.
    Extracts page-numbered text, normalizes, chunks (~500 tokens / 75 overlap),
    embeds with all-MiniLM-L6-v2, and persists in ChromaDB + SQLite.
    """
    file_bytes = await file.read()
    try:
        doc = ingest_document(
            db=db,
            user=admin_user,
            filename=file.filename or "",
            file_bytes=file_bytes,
            title=title,
            category=category,
            ip=_client_ip(request),
        )
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except (DocumentValidationError, DocumentExtractionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return serialize_document(doc)


@router.get("/documents", response_model=DocumentListOut)
def list_knowledge_documents(
    q: Optional[str] = Query(None, max_length=200, description="Search by document name or title"),
    category: Optional[str] = Query(None, max_length=100),
    doc_status: Optional[str] = Query(None, alias="status", max_length=50),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Lists uploaded knowledge documents with optional name/title, category, and status filters."""
    query = db.query(Document).options(joinedload(Document.creator))

    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Document.title.ilike(like),
                Document.filename.ilike(like),
            )
        )
    if category and category != "all":
        query = query.filter(Document.category == category.strip().lower())
    if doc_status and doc_status != "all":
        query = query.filter(Document.status == doc_status.strip().lower())

    docs = query.order_by(Document.created_at.desc(), Document.id.desc()).all()
    return {
        "items": [serialize_document(d) for d in docs],
        "total": len(docs),
    }


@router.get("/documents/{doc_id}", response_model=DocumentDetailOut)
def get_knowledge_document(
    doc_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    doc = (
        db.query(Document)
        .options(joinedload(Document.creator))
        .filter(Document.id == doc_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    data = serialize_document(doc)
    data["content_preview"] = (doc.content or "")[:4000]
    return data


@router.delete("/documents/{doc_id}", response_model=DocumentDeleteResponse)
def delete_knowledge_document(
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Admin-only: deletes document metadata from SQLite, file from disk, and chunks from ChromaDB."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    filename = doc.filename or doc.title
    deleted_chunks = delete_document(db=db, doc=doc, user=admin_user, ip=_client_ip(request))
    return {
        "id": doc_id,
        "filename": filename,
        "deleted_chunks": deleted_chunks,
        "message": f"Deleted document '{filename}' and {deleted_chunks} vector chunk(s).",
    }


@router.post("/documents/{doc_id}/reprocess", response_model=DocumentOut)
def reprocess_knowledge_document(
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Admin-only: re-extracts, re-chunks, re-embeds, and updates ChromaDB vectors for a document."""
    doc = (
        db.query(Document)
        .options(joinedload(Document.creator))
        .filter(Document.id == doc_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        updated = reprocess_document(db=db, doc=doc, user=admin_user, ip=_client_ip(request))
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_document(updated)


@router.get("/search", response_model=SemanticSearchResponse)
def search_knowledge_base(
    q: str = Query(..., min_length=1, max_length=500, description="Semantic search query"),
    top_k: int = Query(5, ge=1, le=20),
    category: Optional[str] = Query(None, max_length=100),
    document_id: Optional[int] = Query(None),
    _current_user: User = Depends(get_current_user),
):
    """Performs semantic similarity search across ChromaDB knowledge chunks."""
    results = semantic_search(
        query=q,
        top_k=top_k,
        category=category,
        document_id=document_id,
    )
    return {
        "query": q.strip(),
        "total": len(results),
        "results": results,
    }
