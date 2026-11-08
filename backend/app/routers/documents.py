import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.config import get_settings
from app.db import get_session
from app.deps import current_user_id, llm_client
from app.models import Chunk, Concept, Document
from app.schemas import ConceptOut, DocumentOut, ExtractionOut, TextDocumentIn
from app.services.extraction import extract_concepts
from app.services.ingest import document_out, ingest_pdf, ingest_text
from app.services.llm import LLMClient

router = APIRouter(prefix="/documents", tags=["documents"])


def _too_big() -> HTTPException:
    mb = get_settings().MAX_UPLOAD_BYTES / (1024 * 1024)
    return HTTPException(413, f"Upload is too large; the limit is {mb:g} MB.")


def _get_owned(session: Session, document_id: int, user_id: int) -> Document:
    doc = session.get(Document, document_id)
    if doc is None or doc.user_id != user_id:
        raise HTTPException(404, "Document not found.")
    return doc


@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(
    request: Request,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
) -> DocumentOut:
    """Accepts JSON {title, text} for pasted text, or multipart with a `file` PDF (+ `title`)."""
    limit = get_settings().MAX_UPLOAD_BYTES
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit + 64 * 1024:  # slack for multipart framing
        raise _too_big()
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()

    if content_type == "application/json":
        body = await request.body()
        if len(body) > limit + 64 * 1024:
            raise _too_big()
        try:
            payload = TextDocumentIn.model_validate_json(body)
        except ValidationError as exc:
            raise HTTPException(422, json.loads(exc.json(include_url=False))) from exc
        if len(payload.text.encode("utf-8")) > limit:
            raise _too_big()
        doc = ingest_text(session, user_id=user_id, title=payload.title, text=payload.text)
    elif content_type == "multipart/form-data":
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(422, "Multipart uploads need a `file` field containing a PDF.")
        data = await upload.read(limit + 1)
        if len(data) > limit:
            raise _too_big()
        title = form.get("title")
        doc = ingest_pdf(
            session,
            user_id=user_id,
            title=title if isinstance(title, str) else None,
            filename=upload.filename,
            data=data,
        )
    else:
        raise HTTPException(
            415, "Send application/json (pasted text) or multipart/form-data (PDF)."
        )
    return document_out(session, doc)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    session: Session = Depends(get_session), user_id: int = Depends(current_user_id)
) -> list[DocumentOut]:
    counts = {
        doc_id: n
        for doc_id, n in session.execute(
            select(Chunk.document_id, func.count())
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.user_id == user_id)
            .group_by(Chunk.document_id)
        )
    }
    docs = session.scalars(
        select(Document).where(Document.user_id == user_id).order_by(Document.id.desc())
    )
    return [
        DocumentOut(
            id=d.id,
            title=d.title,
            source_type=d.source_type,
            original_filename=d.original_filename,
            page_count=d.page_count,
            status=d.status,
            error_message=d.error_message,
            chunk_count=counts.get(d.id, 0),
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
) -> DocumentOut:
    return document_out(session, _get_owned(session, document_id, user_id))


@router.post("/{document_id}/extract-concepts", response_model=ExtractionOut)
def extract_document_concepts(
    document_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
    llm: LLMClient = Depends(llm_client),
) -> ExtractionOut:
    doc = _get_owned(session, document_id, user_id)
    result = extract_concepts(session, doc, llm, user_id)
    concepts = session.scalars(
        select(Concept).where(Concept.document_id == doc.id).order_by(Concept.id)
    )
    return ExtractionOut(
        document=document_out(session, doc),
        created=result.created,
        updated=result.updated,
        model=result.model,
        prompt_version=result.prompt_version,
        concepts=[ConceptOut.model_validate(c) for c in concepts],
    )


@router.get("/{document_id}/concepts", response_model=list[ConceptOut])
def list_concepts(
    document_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
) -> list[ConceptOut]:
    doc = _get_owned(session, document_id, user_id)
    rows = session.scalars(
        select(Concept).where(Concept.document_id == doc.id).order_by(Concept.id)
    )
    return [ConceptOut.model_validate(c) for c in rows]
