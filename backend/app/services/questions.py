from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Concept, Question
from app.prompts.generate_question import (
    PROMPT_VERSION,
    QUESTION_TYPES,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.schemas import GeneratedQuestion
from app.services.llm import LLMClient, LLMError, complete_json
from app.services.practice import chunks_by_ids

MAX_MATERIAL_CHARS = 24_000


def next_question_type(session: Session, concept: Concept) -> str:
    """Rotate explain -> apply -> predict based on how many questions the concept has."""
    count = session.scalar(
        select(func.count()).select_from(Question).where(Question.concept_id == concept.id)
    )
    return QUESTION_TYPES[(count or 0) % len(QUESTION_TYPES)]


def generate_question(
    session: Session, concept: Concept, llm: LLMClient, question_type: str | None
) -> Question:
    chunks = chunks_by_ids(session, concept.source_chunk_ids)
    if not chunks:
        raise HTTPException(422, "This concept has no source chunks to write a question from.")
    qtype = question_type or next_question_type(session, concept)

    material: list[tuple[int, str]] = []
    used = 0
    for chunk in chunks:
        if material and used + len(chunk.text) > MAX_MATERIAL_CHARS:
            break
        material.append((chunk.chunk_index, chunk.text))
        used += len(chunk.text)

    try:
        generated, result = complete_json(
            llm,
            system=SYSTEM_PROMPT,
            user=build_user_prompt(
                concept_name=concept.name,
                definition=concept.definition,
                question_type=qtype,
                chunks=material,
            ),
            schema=GeneratedQuestion,
            tier="strong",
        )
    except LLMError as exc:
        raise HTTPException(502, f"Question generation failed: {exc}") from exc

    question = Question(
        concept_id=concept.id,
        question_type=qtype,
        prompt=generated.prompt,
        rubric=generated.rubric,  # backend-only: a JSON list of key-point strings
        misconceptions=generated.misconceptions or None,  # backend-only
        model=result.model,
        prompt_version=PROMPT_VERSION,
    )
    session.add(question)
    session.commit()
    return question
