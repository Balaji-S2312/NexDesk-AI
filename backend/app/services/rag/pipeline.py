import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.user import User
from app.services.rag.chunker import chunk_pages
from app.services.rag.embeddings import embedding_service
from app.services.rag.extractor import (
    SUPPORTED_EXTENSIONS,
    DocumentExtractionError,
    extract_pages,
)
from app.services.rag.vector_store import vector_store

logger = logging.getLogger(__name__)


class DocumentValidationError(ValueError):
    """Raised when file type, size, or structure validation fails."""


class DocumentTooLargeError(ValueError):
    """Raised when uploaded file exceeds MAX_UPLOAD_SIZE_MB."""


class DuplicateDocumentError(ValueError):
    """Raised when an identical file hash already exists in the knowledge base."""

    def __init__(self, existing: Document):
        self.existing = existing
        super().__init__(
            f"Duplicate document detected: '{existing.filename or existing.title}' (ID #{existing.id}) already exists."
        )


def _sanitize_filename(filename: str) -> str:
    base = os.path.basename(filename or "document.txt")
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return cleaned or "document.txt"


def validate_upload_file(filename: str, file_bytes: bytes) -> str:
    """Validates filename extension, size limits, non-emptiness, and magic header."""
    if not filename or "." not in filename:
        raise DocumentValidationError("Filename must include a valid extension (.pdf, .docx, .txt).")

    ext = filename.rsplit(".", 1)[-1].lower().strip()
    if ext not in SUPPORTED_EXTENSIONS:
        raise DocumentValidationError(
            f"Unsupported file type '.{ext}'. Supported types are: PDF, DOCX, TXT."
        )

    size = len(file_bytes)
    if size == 0:
        raise DocumentValidationError("Uploaded file is empty.")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size > max_bytes:
        raise DocumentTooLargeError(
            f"File size ({size / (1024 * 1024):.2f} MB) exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    # Light magic-byte validation for binary formats
    if ext == "pdf" and not file_bytes.lstrip().startswith(b"%PDF"):
        raise DocumentValidationError("File extension is .pdf, but file header is not a valid PDF.")
    if ext == "docx" and not file_bytes.startswith(b"PK"):
        raise DocumentValidationError("File extension is .docx, but file header is not a valid DOCX archive.")

    return ext


def _write_audit(
    db: Session,
    user: Optional[User],
    action: str,
    doc_id: int,
    details: str,
    ip: Optional[str] = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            resource_type="document",
            resource_id=str(doc_id),
            details=details,
            ip_address=ip,
            created_at=datetime.now(timezone.utc),
        )
    )


def serialize_document(doc: Document) -> Dict[str, Any]:
    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size or 0,
        "file_hash": doc.file_hash,
        "category": doc.category,
        "status": doc.status,
        "error_message": doc.error_message,
        "page_count": doc.page_count or 0,
        "chunk_count": doc.chunk_count or 0,
        "created_by_id": doc.created_by_id,
        "created_by": doc.creator.name if doc.creator else None,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


def ingest_document(
    db: Session,
    user: User,
    filename: str,
    file_bytes: bytes,
    title: Optional[str] = None,
    category: str = "general",
    ip: Optional[str] = None,
) -> Document:
    """
    Executes the full 10-step RAG document ingestion pipeline:
    validate -> duplicate check -> extract (with page numbers) -> normalize -> chunk ->
    embed (all-MiniLM-L6-v2) -> store in ChromaDB -> save SQLite metadata -> audit.
    """
    ext = validate_upload_file(filename, file_bytes)
    safe_name = _sanitize_filename(filename)
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    existing = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing:
        raise DuplicateDocumentError(existing)

    # Extract and normalize pages before persisting so corrupted uploads don't pollute storage
    pages = extract_pages(file_bytes, ext)
    full_text = "\n\n".join(f"[Page {p.page_number}]\n{p.text}" for p in pages)
    chunks = chunk_pages(
        pages,
        chunk_size_tokens=settings.CHUNK_SIZE_TOKENS,
        overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
    )
    if not chunks:
        raise DocumentExtractionError("Document produced zero chunks after text normalization.")

    # Save raw file to disk for future reprocessing
    os.makedirs(settings.KNOWLEDGE_UPLOAD_DIR, exist_ok=True)
    disk_path = os.path.join(settings.KNOWLEDGE_UPLOAD_DIR, f"{file_hash[:16]}_{safe_name}")
    with open(disk_path, "wb") as f:
        f.write(file_bytes)

    doc_title = (title or os.path.splitext(safe_name)[0].replace("_", " ").replace("-", " ")).strip()
    if not doc_title:
        doc_title = safe_name

    now = datetime.now(timezone.utc)
    doc = Document(
        title=doc_title[:255],
        filename=safe_name[:255],
        content=full_text,
        file_path=disk_path,
        file_type=ext,
        file_size=len(file_bytes),
        file_hash=file_hash,
        category=(category or "general").strip().lower(),
        status="processing",
        page_count=max(p.page_number for p in pages),
        chunk_count=0,
        created_by_id=user.id,
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(doc)
        db.flush()  # obtain doc.id

        # Generate 384-dim embeddings (model loaded once and reused)
        embeddings = embedding_service.embed_texts([c.text for c in chunks])

        # Store embeddings + metadata in persistent ChromaDB
        stored_count = vector_store.add_document_chunks(
            document_id=doc.id,
            source_filename=safe_name,
            title=doc.title,
            category=doc.category,
            chunks=chunks,
            embeddings=embeddings,
        )

        doc.chunk_count = stored_count
        doc.status = "completed"
        doc.error_message = None
        doc.updated_at = datetime.now(timezone.utc)

        _write_audit(
            db,
            user,
            "UPLOAD_DOCUMENT",
            doc.id,
            f"Ingested '{safe_name}' ({doc.page_count} pages, {stored_count} chunks)",
            ip=ip,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        if doc.id:
            try:
                vector_store.delete_document_chunks(doc.id)
            except Exception:
                logger.exception("Cleanup of Chroma chunks failed for doc %s", doc.id)
        if os.path.exists(disk_path):
            try:
                os.remove(disk_path)
            except OSError:
                pass
        raise exc

    db.refresh(doc)
    return doc


def reprocess_document(
    db: Session,
    doc: Document,
    user: User,
    ip: Optional[str] = None,
) -> Document:
    """Re-extracts, re-chunks, and re-embeds an existing document and replaces its ChromaDB chunks."""
    doc.status = "processing"
    doc.error_message = None
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()

    try:
        if doc.file_path and os.path.exists(doc.file_path):
            with open(doc.file_path, "rb") as f:
                file_bytes = f.read()
            pages = extract_pages(file_bytes, doc.file_type)
            full_text = "\n\n".join(f"[Page {p.page_number}]\n{p.text}" for p in pages)
            doc.content = full_text
            doc.page_count = max(p.page_number for p in pages)
        elif doc.content:
            from app.services.rag.extractor import PageContent, normalize_text
            pages = [PageContent(page_number=1, text=normalize_text(doc.content))]
            doc.page_count = 1
        else:
            raise DocumentExtractionError("Source file and text content are unavailable for reprocessing.")

        chunks = chunk_pages(
            pages,
            chunk_size_tokens=settings.CHUNK_SIZE_TOKENS,
            overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
        )
        embeddings = embedding_service.embed_texts([c.text for c in chunks])

        # Replace existing chunks cleanly
        vector_store.delete_document_chunks(doc.id)
        stored_count = vector_store.add_document_chunks(
            document_id=doc.id,
            source_filename=doc.filename or doc.title,
            title=doc.title,
            category=doc.category,
            chunks=chunks,
            embeddings=embeddings,
        )

        doc.chunk_count = stored_count
        doc.status = "completed"
        doc.error_message = None
        doc.updated_at = datetime.now(timezone.utc)

        _write_audit(
            db,
            user,
            "REPROCESS_DOCUMENT",
            doc.id,
            f"Reprocessed '{doc.filename or doc.title}' ({doc.page_count} pages, {stored_count} chunks)",
            ip=ip,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        doc.status = "failed"
        doc.error_message = str(exc)
        doc.updated_at = datetime.now(timezone.utc)
        db.commit()
        raise

    db.refresh(doc)
    return doc


def delete_document(
    db: Session,
    doc: Document,
    user: User,
    ip: Optional[str] = None,
) -> int:
    """Deletes a document's chunks from ChromaDB, removes stored file, and removes SQLite record."""
    doc_id = doc.id
    filename = doc.filename or doc.title
    file_path = doc.file_path

    deleted_chunks = vector_store.delete_document_chunks(doc_id)

    try:
        db.delete(doc)
        _write_audit(
            db,
            user,
            "DELETE_DOCUMENT",
            doc_id,
            f"Deleted '{filename}' and {deleted_chunks} vector chunks",
            ip=ip,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            logger.warning("Could not remove file on disk: %s", file_path)

    return deleted_chunks


def semantic_search(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
    document_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Embeds a user query and retrieves top-k semantically matching chunks from ChromaDB."""
    clean_query = (query or "").strip()
    if not clean_query:
        return []
    query_vec = embedding_service.embed_query(clean_query)
    return vector_store.search(
        query_embedding=query_vec,
        top_k=top_k,
        category=category,
        document_id=document_id,
    )
