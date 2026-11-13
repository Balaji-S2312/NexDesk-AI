import math
import re
from dataclasses import dataclass
from typing import List

from app.services.rag.extractor import PageContent


@dataclass
class TextChunk:
    chunk_index: int
    page_number: int
    text: str
    token_count: int


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[^\sA-Za-z0-9]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def count_tokens(text: str) -> int:
    """
    Deterministic, fast token estimator aligned with WordPiece/BPE subword counts.
    Alphanumeric tokens longer than 8 chars contribute extra subword tokens.
    """
    if not text:
        return 0
    total = 0
    for tok in _TOKEN_RE.findall(text):
        length = len(tok)
        if length <= 8:
            total += 1
        else:
            total += math.ceil(length / 5)
    return total


def _split_into_units(text: str, max_tokens: int) -> List[str]:
    """Splits text cleanly by paragraph -> sentence -> words so no unit exceeds max_tokens."""
    units: List[str] = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if count_tokens(para) <= max_tokens:
            units.append(para)
            continue

        for sent in _SENTENCE_SPLIT_RE.split(para):
            sent = sent.strip()
            if not sent:
                continue
            if count_tokens(sent) <= max_tokens:
                units.append(sent)
                continue

            # Hard word-level split for oversized single sentences
            words = sent.split()
            buf: List[str] = []
            buf_tokens = 0
            for w in words:
                wt = count_tokens(w)
                if buf and buf_tokens + wt > max_tokens:
                    units.append(" ".join(buf))
                    buf = [w]
                    buf_tokens = wt
                else:
                    buf.append(w)
                    buf_tokens += wt
            if buf:
                units.append(" ".join(buf))
    return units


def chunk_pages(
    pages: List[PageContent],
    chunk_size_tokens: int = 500,
    overlap_tokens: int = 75,
) -> List[TextChunk]:
    """
    Splits page-numbered text into token-aware overlapping chunks (~500 tokens, ~75 overlap),
    preserving the exact page number for each chunk.
    """
    if chunk_size_tokens <= 0:
        raise ValueError("chunk_size_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= chunk_size_tokens:
        raise ValueError("overlap_tokens must be >= 0 and < chunk_size_tokens")

    chunks: List[TextChunk] = []
    chunk_index = 0

    for page in pages:
        units = _split_into_units(page.text, max_tokens=chunk_size_tokens)
        if not units:
            continue

        current_units: List[str] = []
        current_tokens = 0

        for unit in units:
            u_tokens = count_tokens(unit)
            if current_units and current_tokens + u_tokens > chunk_size_tokens:
                chunk_text = "\n\n".join(current_units).strip()
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        text=chunk_text,
                        token_count=count_tokens(chunk_text),
                    )
                )
                chunk_index += 1

                # Build overlap window from trailing units of the just-emitted chunk
                overlap_buf: List[str] = []
                overlap_count = 0
                for prev_unit in reversed(current_units):
                    pt = count_tokens(prev_unit)
                    if overlap_count + pt <= overlap_tokens:
                        overlap_buf.insert(0, prev_unit)
                        overlap_count += pt
                    else:
                        break

                # Ensure forward progress even if unit + overlap exceeds chunk_size_tokens
                while overlap_buf and (overlap_count + u_tokens > chunk_size_tokens):
                    removed = overlap_buf.pop(0)
                    overlap_count -= count_tokens(removed)

                current_units = overlap_buf + [unit]
                current_tokens = overlap_count + u_tokens
            else:
                current_units.append(unit)
                current_tokens += u_tokens

        if current_units:
            chunk_text = "\n\n".join(current_units).strip()
            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    text=chunk_text,
                    token_count=count_tokens(chunk_text),
                )
            )
            chunk_index += 1

    return chunks
