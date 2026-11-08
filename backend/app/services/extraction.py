"""Concept extraction: chunks -> LLM -> validated, deduped concepts stored idempotently."""

import re
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, Concept, Document
from app.prompts.extract_concepts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.schemas import ConceptExtraction
from app.services.events import log_event
from app.services.llm import LLMClient, LLMError, complete_json

MAX_CONCEPTS = 25


def normalize_name(name: str) -> str:
    return re.sub(r"[\W_]+", " ", name.casefold()).strip()


@dataclass
class ExtractionResult:
    created: int
    updated: int
    model: str
    prompt_version: str


def _fail(session: Session, doc: Document, user_id: int, message: str, status: int) -> None:
    doc.status = "failed"
    doc.error_message = message
    log_event(
        session,
        user_id=user_id,
        event_type="concepts_extracted",
        document_id=doc.id,
        payload={"success": False, "error": message, "prompt_version": PROMPT_VERSION},
    )
    session.commit()
    raise HTTPException(status, message)


def extract_concepts(
    session: Session, doc: Document, llm: LLMClient, user_id: int
) -> ExtractionResult:
    chunks = list(
        session.scalars(
            select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index)
        )
    )
    if not chunks:
        raise HTTPException(422, "This document has no text to extract concepts from.")
    if sum(len(c.text) for c in chunks) > get_settings().MAX_EXTRACTION_CHARS:
        _fail(session, doc, user_id, "Document is too long to extract concepts in one pass.", 422)

    doc.status = "processing"
    doc.error_message = None
    session.commit()  # so clients polling GET /documents/{id} can see "processing"

    try:
        parsed, result = complete_json(
            llm,
            system=SYSTEM_PROMPT,
            user=build_user_prompt([(c.chunk_index, c.text) for c in chunks]),
            schema=ConceptExtraction,
        )
    except LLMError as exc:
        _fail(session, doc, user_id, f"Concept extraction failed: {exc}", 502)

    index_to_id = {c.chunk_index: c.id for c in chunks}

    # Validate chunk indexes, drop ungrounded concepts, dedupe by normalized name.
    accepted: dict[str, tuple[str, str, list[int]]] = {}
    for item in parsed.concepts:
        key = normalize_name(item.name)
        ids = [index_to_id[i] for i in dict.fromkeys(item.chunk_indexes) if i in index_to_id]
        if not key or not item.definition or not ids:
            continue
        if key in accepted:
            name, definition, existing_ids = accepted[key]
            accepted[key] = (name, definition, list(dict.fromkeys(existing_ids + ids)))
        else:
            accepted[key] = (item.name, item.definition, ids)
    selected = list(accepted.items())[:MAX_CONCEPTS]
    if not selected:
        _fail(session, doc, user_id, "The model returned no usable concepts.", 502)

    existing = {
        normalize_name(c.name): c
        for c in session.scalars(select(Concept).where(Concept.document_id == doc.id))
    }
    created = updated = 0
    for key, (name, definition, ids) in selected:
        current = existing.get(key)
        if current is None:
            session.add(
                Concept(
                    document_id=doc.id,
                    name=name,
                    definition=definition,
                    source_chunk_ids=ids,
                    origin="model",
                    model=result.model,
                    prompt_version=PROMPT_VERSION,
                )
            )
            created += 1
        elif current.origin == "model":
            current.definition = definition
            current.source_chunk_ids = ids
            current.model = result.model
            current.prompt_version = PROMPT_VERSION
            updated += 1
        # concepts the learner added themselves are never overwritten

    doc.status = "ready"
    doc.error_message = None
    log_event(
        session,
        user_id=user_id,
        event_type="concepts_extracted",
        document_id=doc.id,
        payload={
            "success": True,
            "concept_count": len(selected),
            "created": created,
            "updated": updated,
            "chunk_count": len(chunks),
            "model": result.model,
            "prompt_version": PROMPT_VERSION,
        },
    )
    session.commit()
    return ExtractionResult(created, updated, result.model, PROMPT_VERSION)
