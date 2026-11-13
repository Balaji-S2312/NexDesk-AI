import io
import re
import unicodedata
from dataclasses import dataclass
from typing import List

import fitz  # PyMuPDF
from docx import Document as DocxDocument


class DocumentExtractionError(ValueError):
    """Raised when a document cannot be parsed or contains no extractable text."""


@dataclass
class PageContent:
    page_number: int
    text: str


SUPPORTED_EXTENSIONS = {"pdf", "docx", "txt"}


def normalize_text(text: str) -> str:
    """Normalizes Unicode, line endings, and whitespace while keeping paragraph breaks."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove control chars except newline and tab
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse horizontal whitespace per line
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    cleaned = "\n".join(lines)
    # Collapse 3+ consecutive newlines to 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_pdf(file_bytes: bytes) -> List[PageContent]:
    pages: List[PageContent] = []
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf_doc:
            for idx, page in enumerate(pdf_doc, start=1):
                raw = page.get_text("text") or ""
                norm = normalize_text(raw)
                if norm:
                    pages.append(PageContent(page_number=idx, text=norm))
    except Exception as exc:
        raise DocumentExtractionError(f"Failed to parse PDF document: {exc}") from exc

    if not pages:
        raise DocumentExtractionError("PDF contains no extractable text.")
    return pages


def _extract_docx(file_bytes: bytes) -> List[PageContent]:
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
    except Exception as exc:
        raise DocumentExtractionError(f"Failed to parse DOCX document: {exc}") from exc

    pages: List[PageContent] = []
    current_page = 1
    current_blocks: List[str] = []

    def flush_page() -> None:
        nonlocal current_blocks
        combined = normalize_text("\n\n".join(current_blocks))
        if combined:
            pages.append(PageContent(page_number=current_page, text=combined))
        current_blocks = []

    # Iterate body children in order (paragraphs and tables)
    for child in doc.element.body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            # Check for explicit page break inside paragraph XML
            xml_str = child.xml
            has_page_break = (
                'w:type="page"' in xml_str
                or "lastRenderedPageBreak" in xml_str
            )
            para_text = "".join(child.itertext()).strip()
            if para_text:
                current_blocks.append(para_text)
            if has_page_break and current_blocks:
                flush_page()
                current_page += 1
        elif tag == "tbl":
            row_texts: List[str] = []
            for tr in child.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
                cells = []
                for tc in tr.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"):
                    cell_text = " ".join("".join(tc.itertext()).split())
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    row_texts.append(" | ".join(cells))
            if row_texts:
                current_blocks.append("\n".join(row_texts))

    flush_page()

    if not pages:
        raise DocumentExtractionError("DOCX contains no extractable text.")
    return pages


def _extract_txt(file_bytes: bytes) -> List[PageContent]:
    text = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise DocumentExtractionError("Failed to decode text document.")

    # Preserve form-feed page breaks if present
    raw_pages = text.split("\f")
    pages: List[PageContent] = []
    for idx, raw_page in enumerate(raw_pages, start=1):
        norm = normalize_text(raw_page)
        if norm:
            pages.append(PageContent(page_number=idx, text=norm))

    if not pages:
        raise DocumentExtractionError("Text file is empty or contains no readable content.")
    return pages


def extract_pages(file_bytes: bytes, file_type: str) -> List[PageContent]:
    """Extracts normalized, page-numbered text blocks from PDF, DOCX, or TXT bytes."""
    ext = file_type.lower().lstrip(".")
    if ext == "pdf":
        return _extract_pdf(file_bytes)
    if ext == "docx":
        return _extract_docx(file_bytes)
    if ext == "txt":
        return _extract_txt(file_bytes)
    raise DocumentExtractionError(f"Unsupported file type: {file_type}")
