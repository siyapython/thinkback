"""The hint ladder: generate the next level, leak-check it, regenerate once, else fall back."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Answer, Attempt, Concept, Document, HintRequest, Question
from app.prompts.hint import (
    FALLBACK_HINTS,
    PROMPT_VERSION,
    STRICT_SUFFIX,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.services.events import log_event
from app.services.leak import check_leak, hint_shape_ok
from app.services.llm import LLMClient, LLMError
from app.services.practice import chunks_by_ids, require_in_progress

MAX_LEVEL = 4
MAX_SOURCE_CHARS = 6000
FALLBACK_MODEL = "static-fallback"


def notes_location(document: Document, pages: list[tuple[int | None, int | None]]) -> str:
    starts = [s for s, _ in pages if s is not None]
    ends = [e for _, e in pages if e is not None]
    if starts and ends:
        lo, hi = min(starts), max(ends)
        span = f"page {lo}" if lo == hi else f"pages {lo}-{hi}"
        return f'{span} of your notes "{document.title}"'
    return f'the section of your notes "{document.title}" about this concept'


def _try_generate(
    llm: LLMClient, *, system: str, user: str, rubric: list[str], exclude: str
) -> tuple[str | None, str | None]:
    """One generation attempt. Returns (hint_text_if_it_passes, model_name)."""
    try:
        result = llm.complete(system=system, user=user, max_tokens=400, tier="fast")
    except LLMError:
        return None, None
    text = result.text.strip()
    if hint_shape_ok(text) and not check_leak(text, rubric, exclude=exclude).leaked:
        return text, result.model
    return None, result.model


def request_hint(session: Session, attempt: Attempt, llm: LLMClient) -> HintRequest:
    require_in_progress(attempt)
    if attempt.max_hint_level >= MAX_LEVEL:
        raise HTTPException(409, "You have already used all 4 hint levels for this attempt.")
    level = attempt.max_hint_level + 1

    question = session.get(Question, attempt.question_id)
    concept = session.get(Concept, question.concept_id)
    document = session.get(Document, concept.document_id)
    chunks = chunks_by_ids(session, concept.source_chunk_ids)
    rubric: list[str] = list(question.rubric)
    latest_answer = session.scalar(
        select(Answer.answer_text)
        .where(Answer.attempt_id == attempt.id)
        .order_by(Answer.id.desc())
        .limit(1)
    )
    location = notes_location(document, [(c.page_start, c.page_end) for c in chunks])
    material = "\n\n".join(c.text for c in chunks)[:MAX_SOURCE_CHARS]
    user_prompt = build_user_prompt(
        level=level,
        concept_name=concept.name,
        question=question.prompt,
        notes_location=location,
        source_material=material,
        rubric=rubric,
        latest_answer=latest_answer,
    )
    exclude = f"{question.prompt} {concept.name}"

    regenerated = False
    model = FALLBACK_MODEL
    text, used_model = _try_generate(
        llm, system=SYSTEM_PROMPT, user=user_prompt, rubric=rubric, exclude=exclude
    )
    if text is None:
        regenerated = True
        text, retry_model = _try_generate(
            llm,
            system=SYSTEM_PROMPT + STRICT_SUFFIX,
            user=user_prompt,
            rubric=rubric,
            exclude=exclude,
        )
        used_model = retry_model or used_model
    used_fallback = text is None
    if used_fallback:
        text = FALLBACK_HINTS[level].format(notes_location=location)
    else:
        model = used_model or model

    hint = HintRequest(
        attempt_id=attempt.id,
        level=level,
        hint_text=text,
        cited_chunk_ids=[c.id for c in chunks],
        leak_check_passed=not used_fallback,  # False means the model's output never passed
        regenerated=regenerated,
        model=model,
        prompt_version=PROMPT_VERSION,
    )
    session.add(hint)
    attempt.max_hint_level = level
    log_event(
        session,
        user_id=attempt.user_id,
        event_type="hint_requested",
        document_id=concept.document_id,
        concept_id=concept.id,
        question_id=question.id,
        attempt_id=attempt.id,
        payload={
            "level": level,
            "leak_check_passed": hint.leak_check_passed,
            "regenerated": regenerated,
            "used_fallback": used_fallback,
            "model": model,
            "prompt_version": PROMPT_VERSION,
        },
    )
    session.commit()
    return hint
