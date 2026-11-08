"""Turn an upload (pasted text or PDF) into a document row, chunks and an event."""

import hashlib
import os
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, Document
from app.schemas import DocumentOut
from app.services.chunking import chunk_pages, clean_text
from app.services.events import log_event
from app.services.pdf import extract_pdf_pages

NO_TEXT_MESSAGE = (
    "No extractable text was found in this PDF. It is probably scanned images; "
    "try a text-based PDF or paste the text instead."
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def document_out(session: Session, doc: Document) -> DocumentOut:
    count = session.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == doc.id)
    )
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        source_type=doc.source_type,
        original_filename=doc.original_filename,
        page_count=doc.page_count,
        status=doc.status,
        error_message=doc.error_message,
        chunk_count=count or 0,
        created_at=doc.created_at,
    )


def _raise_duplicate(existing_id: int) -> None:
    raise HTTPException(
        409, f"You already uploaded this exact content (document id {existing_id})."
    )


def _check_duplicate(session: Session, user_id: int, content_hash: str) -> None:
    existing = session.scalar(
        select(Document.id).where(
            Document.user_id == user_id, Document.content_hash == content_hash
        )
    )
    if existing is not None:
        _raise_duplicate(existing)


def _store(
    session: Session,
    *,
    user_id: int,
    title: str,
    source_type: str,
    content_hash: str,
    pages: list[tuple[int | None, str]],
    page_count: int | None,
    original_filename: str | None = None,
    file_bytes: bytes | None = None,
) -> Document:
    chunks = chunk_pages(pages)
    doc = Document(
        user_id=user_id,
        title=title.strip(),
        source_type=source_type,
        original_filename=original_filename,
        page_count=page_count,
        content_hash=content_hash,
        status="uploaded" if chunks else "failed",
        error_message=None if chunks else NO_TEXT_MESSAGE,
    )
    session.add(doc)
    session.flush()

    saved_path: Path | None = None
    if file_bytes is not None:
        upload_dir = get_settings().UPLOAD_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / f"{user_id}-{content_hash}.pdf"  # name never comes from the user
        saved_path.write_bytes(file_bytes)
        doc.file_path = str(saved_path)

    session.add_all(
        Chunk(
            document_id=doc.id,
            chunk_index=c.chunk_index,
            text=c.text,
            page_start=c.page_start,
            page_end=c.page_end,
            token_count=c.token_count,
        )
        for c in chunks
    )
    log_event(
        session,
        user_id=user_id,
        event_type="document_uploaded",
        document_id=doc.id,
        payload={
            "source_type": source_type,
            "page_count": page_count,
            "chunk_count": len(chunks),
            "char_count": sum(len(t) for _, t in pages),
            "size_bytes": len(file_bytes) if file_bytes is not None else None,
            "status": doc.status,
        },
    )
    try:
        session.commit()
    except IntegrityError:  # two identical uploads raced past the duplicate check
        session.rollback()
        if saved_path is not None:
            _safe_unlink(saved_path)
        raise HTTPException(409, "You already uploaded this exact content.") from None
    return doc


def _safe_unlink(path: Path) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def ingest_text(session: Session, *, user_id: int, title: str, text: str) -> Document:
    text = clean_text(text)
    if not text.strip():
        raise HTTPException(422, "The text is empty.")
    content_hash = sha256_hex(text.encode("utf-8"))
    _check_duplicate(session, user_id, content_hash)
    return _store(
        session,
        user_id=user_id,
        title=title,
        source_type="text",
        content_hash=content_hash,
        pages=[(None, text)],
        page_count=None,
    )


def ingest_pdf(
    session: Session, *, user_id: int, title: str | None, filename: str | None, data: bytes
) -> Document:
    content_hash = sha256_hex(data)
    _check_duplicate(session, user_id, content_hash)
    page_texts = extract_pdf_pages(data, get_settings().MAX_PAGES)
    # Only the base name is kept, and only as a label; it is never used to build a path.
    label = os.path.basename(filename.replace("\\", "/")) if filename else None
    stem = os.path.splitext(label)[0] if label else ""
    return _store(
        session,
        user_id=user_id,
        title=(title or "").strip() or stem or "Untitled PDF",
        source_type="pdf",
        content_hash=content_hash,
        pages=[(n, t) for n, t in enumerate(page_texts, start=1)],
        page_count=len(page_texts),
        original_filename=label,
        file_bytes=data,
    )
