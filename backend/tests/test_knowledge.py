import io
from pathlib import Path
from typing import Dict

import docx
import fitz
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.init_db import (
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_PASSWORD,
    DEMO_EMPLOYEE_EMAIL,
    DEMO_EMPLOYEE_PASSWORD,
)
from app.main import app
from app.services.rag.chunker import chunk_pages, count_tokens
from app.services.rag.embeddings import EMBEDDING_DIMENSION, embedding_service
from app.services.rag.extractor import PageContent
from app.services.rag.vector_store import vector_store


client = TestClient(app)


def _login_headers(email: str, password: str) -> Dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _build_pdf_bytes(pages_text: list[str]) -> bytes:
    pdf_doc = fitz.open()
    for text in pages_text:
        page = pdf_doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    data = pdf_doc.tobytes()
    pdf_doc.close()
    return data


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for para in paragraphs:
        document.add_paragraph(para)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture(scope="module", autouse=True)
def isolated_rag_storage(tmp_path_factory: pytest.TempPathFactory):
    """Isolate ChromaDB and uploaded knowledge files for this test module."""
    temp_root = tmp_path_factory.mktemp("rag_module_test")
    uploads_dir = temp_root / "uploads"
    chroma_dir = temp_root / "chroma_db"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    original_upload_dir = settings.KNOWLEDGE_UPLOAD_DIR
    original_chroma_dir = settings.CHROMA_PERSIST_DIRECTORY

    settings.KNOWLEDGE_UPLOAD_DIR = str(uploads_dir)
    settings.CHROMA_PERSIST_DIRECTORY = str(chroma_dir)
    vector_store.reset_for_testing(str(chroma_dir))

    yield

    settings.KNOWLEDGE_UPLOAD_DIR = original_upload_dir
    settings.CHROMA_PERSIST_DIRECTORY = original_chroma_dir
    vector_store.reset_for_testing(original_chroma_dir)


def test_chunker_token_limits_and_overlap():
    long_sentences = " ".join(
        [
            f"Sentence {idx} describes enterprise VPN routing, DNS resolution, and certificate renewal steps."
            for idx in range(1, 95)
        ]
    )
    chunks = chunk_pages(
        [
            PageContent(page_number=1, text=long_sentences),
            PageContent(page_number=2, text="Short page two guidance for printer queue restarts."),
        ],
        chunk_size_tokens=500,
        overlap_tokens=75,
    )
    assert len(chunks) >= 3
    page_one_chunks = [c for c in chunks if c.page_number == 1]
    page_two_chunks = [c for c in chunks if c.page_number == 2]
    assert len(page_one_chunks) >= 2
    assert len(page_two_chunks) == 1
    for chunk in chunks:
        assert 0 < count_tokens(chunk.text) <= 500
    # Verify overlap preserves tail words between consecutive page-1 chunks
    tail_word = page_one_chunks[0].text.split()[-1]
    assert tail_word in page_one_chunks[1].text


def test_embedding_model_singleton_and_dimension():
    model_a = embedding_service.get_model()
    model_b = embedding_service.get_model()
    assert model_a is model_b

    vectors = embedding_service.embed_texts(["GlobalProtect VPN certificate troubleshooting"])
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIMENSION == 384


def test_knowledge_rbac_and_validation(monkeypatch: pytest.MonkeyPatch):
    admin_headers = _login_headers(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
    employee_headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)

    # Unauthenticated blocked
    unauth_resp = client.get("/api/knowledge/documents")
    assert unauth_resp.status_code == 401

    # Employee cannot upload
    emp_upload = client.post(
        "/api/knowledge/upload",
        headers=employee_headers,
        files={"file": ("notes.txt", b"Hello IT policy", "text/plain")},
    )
    assert emp_upload.status_code == 403

    # Unsupported extension -> 422
    bad_ext = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
    )
    assert bad_ext.status_code == 422

    # Empty file -> 422
    empty_file = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        files={"file": ("empty.txt", b"   ", "text/plain")},
    )
    assert empty_file.status_code == 422

    # Invalid PDF bytes -> 422
    fake_pdf = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        files={"file": ("broken.pdf", b"not actually pdf bytes", "application/pdf")},
    )
    assert fake_pdf.status_code == 422

    # Oversized upload -> 413
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)
    oversized = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        files={"file": ("big.txt", b"Some non-empty content", "text/plain")},
    )
    assert oversized.status_code == 413


def test_end_to_end_pdf_docx_txt_search_reprocess_and_delete():
    admin_headers = _login_headers(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
    employee_headers = _login_headers(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD)

    # 1. Upload a multi-page PDF
    pdf_bytes = _build_pdf_bytes(
        [
            (
                "Page 1: Enterprise GlobalProtect VPN Troubleshooting Guide. "
                "If your VPN client fails with certificate validation error 403, refresh the corporate "
                "root certificate in Keychain or Credential Manager and switch gateway to vpn-us-east.nexdesk.ai."
            ),
            (
                "Page 2: Okta Hardware Token and MFA Reset Procedure. "
                "When an employee loses their YubiKey or Authenticator device, Identity Admins issue "
                "a temporary 8-hour bypass code after verifying manager approval in Service Desk."
            ),
        ]
    )
    pdf_upload = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        data={"title": "VPN and MFA Playbook", "category": "network"},
        files={"file": ("vpn_and_mfa_guide.pdf", pdf_bytes, "application/pdf")},
    )
    assert pdf_upload.status_code == 201, pdf_upload.text
    pdf_doc = pdf_upload.json()
    pdf_id = pdf_doc["id"]
    assert pdf_doc["status"] == "completed"
    assert pdf_doc["filename"] == "vpn_and_mfa_guide.pdf"
    assert pdf_doc["page_count"] == 2
    assert pdf_doc["chunk_count"] >= 2
    assert pdf_doc["file_hash"]

    # Verify ChromaDB vector storage directly
    stored_chunks = vector_store.get_document_chunks(pdf_id, include_embeddings=True)
    assert len(stored_chunks) == pdf_doc["chunk_count"]
    assert {chunk["metadata"]["page_number"] for chunk in stored_chunks} == {1, 2}
    assert all(chunk["metadata"]["source_filename"] == "vpn_and_mfa_guide.pdf" for chunk in stored_chunks)
    assert all(len(chunk["embedding"]) == 384 for chunk in stored_chunks)

    # 2. Duplicate upload detection -> 409 Conflict
    dup_upload = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        files={"file": ("vpn_copy.pdf", pdf_bytes, "application/pdf")},
    )
    assert dup_upload.status_code == 409

    # 3. Upload DOCX and TXT
    docx_bytes = _build_docx_bytes(
        [
            "Corporate Laptop Onboarding Checklist",
            "Install BitLocker encryption, SentinelOne EDR agent, and configure Microsoft 365 Outlook profile.",
        ]
    )
    docx_upload = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        data={"category": "hardware"},
        files={
            "file": (
                "laptop_onboarding.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert docx_upload.status_code == 201, docx_upload.text
    docx_doc = docx_upload.json()
    assert docx_doc["status"] == "completed"
    assert docx_doc["file_type"] == "docx"

    txt_upload = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        data={"category": "email"},
        files={
            "file": (
                "shared_mailbox_sop.txt",
                b"To request a shared Exchange mailbox, submit an Access Management ticket with owner email.",
                "text/plain",
            )
        },
    )
    assert txt_upload.status_code == 201, txt_upload.text
    txt_doc = txt_upload.json()
    assert txt_doc["status"] == "completed"
    assert txt_doc["file_type"] == "txt"

    # 4. List & search by document name (employee allowed)
    list_all = client.get("/api/knowledge/documents", headers=employee_headers)
    assert list_all.status_code == 200
    assert list_all.json()["total"] == 3

    list_by_name = client.get("/api/knowledge/documents?q=vpn_and_mfa", headers=employee_headers)
    assert list_by_name.status_code == 200
    assert list_by_name.json()["total"] == 1
    assert list_by_name.json()["items"][0]["id"] == pdf_id

    detail_resp = client.get(f"/api/knowledge/documents/{pdf_id}", headers=employee_headers)
    assert detail_resp.status_code == 200
    assert "GlobalProtect VPN" in detail_resp.json()["content_preview"]

    # 5. Semantic search verifies relevant chunks + page numbers
    vpn_search = client.get(
        "/api/knowledge/search",
        headers=employee_headers,
        params={"q": "How do I fix GlobalProtect VPN certificate error 403?", "top_k": 3},
    )
    assert vpn_search.status_code == 200, vpn_search.text
    vpn_results = vpn_search.json()["results"]
    assert len(vpn_results) >= 1
    assert vpn_results[0]["document_id"] == pdf_id
    assert vpn_results[0]["page_number"] == 1
    assert vpn_results[0]["source_filename"] == "vpn_and_mfa_guide.pdf"
    assert vpn_results[0]["score"] > 0.2

    mfa_search = client.get(
        "/api/knowledge/search",
        headers=employee_headers,
        params={"q": "Lost YubiKey temporary 8-hour bypass code Okta MFA reset", "top_k": 3},
    )
    assert mfa_search.status_code == 200
    mfa_results = mfa_search.json()["results"]
    assert mfa_results[0]["document_id"] == pdf_id
    assert mfa_results[0]["page_number"] == 2

    # 6. Employee forbidden from reprocess and delete
    emp_reprocess = client.post(f"/api/knowledge/documents/{pdf_id}/reprocess", headers=employee_headers)
    assert emp_reprocess.status_code == 403
    emp_delete = client.delete(f"/api/knowledge/documents/{pdf_id}", headers=employee_headers)
    assert emp_delete.status_code == 403

    # 7. Admin reprocess keeps chunk count clean without duplicates
    reprocess_resp = client.post(f"/api/knowledge/documents/{pdf_id}/reprocess", headers=admin_headers)
    assert reprocess_resp.status_code == 200, reprocess_resp.text
    reprocessed = reprocess_resp.json()
    assert reprocessed["status"] == "completed"
    assert reprocessed["chunk_count"] == pdf_doc["chunk_count"]
    assert len(vector_store.get_document_chunks(pdf_id)) == pdf_doc["chunk_count"]

    # 8. Admin delete removes SQLite row, file on disk, and ChromaDB vectors
    stored_file_path = Path(settings.KNOWLEDGE_UPLOAD_DIR)
    assert any(stored_file_path.iterdir())

    delete_resp = client.delete(f"/api/knowledge/documents/{pdf_id}", headers=admin_headers)
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json()["deleted_chunks"] == pdf_doc["chunk_count"]

    assert client.get(f"/api/knowledge/documents/{pdf_id}", headers=admin_headers).status_code == 404
    assert vector_store.get_document_chunks(pdf_id) == []

    # Semantic search should no longer return deleted document chunks
    after_delete_search = client.get(
        "/api/knowledge/search",
        headers=employee_headers,
        params={"q": "GlobalProtect VPN certificate error 403", "top_k": 5},
    )
    assert after_delete_search.status_code == 200
    assert all(r["document_id"] != pdf_id for r in after_delete_search.json()["results"])

    # Re-uploading the deleted PDF should now succeed cleanly (duplicate record was removed)
    reupload = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        files={"file": ("vpn_and_mfa_guide.pdf", pdf_bytes, "application/pdf")},
    )
    assert reupload.status_code == 201
