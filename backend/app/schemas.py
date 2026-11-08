from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TextDocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)

    @field_validator("title", "text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class DocumentOut(BaseModel):
    """Deliberately has no file_path or content_hash: internals stay internal."""

    id: int
    title: str
    source_type: str
    original_filename: str | None
    page_count: int | None
    status: str
    error_message: str | None
    chunk_count: int
    created_at: datetime


class ConceptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    definition: str
    source_chunk_ids: list[int]
    origin: str
    is_active: bool
    model: str | None
    prompt_version: str | None
    created_at: datetime


class ExtractionOut(BaseModel):
    document: DocumentOut
    created: int
    updated: int
    model: str
    prompt_version: str
    concepts: list[ConceptOut]


# What we require from the model's JSON (validated before anything is stored).
class ExtractedConcept(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    definition: str = Field(min_length=1, max_length=2000)
    chunk_indexes: list[int]

    @field_validator("name", "definition")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class ConceptExtraction(BaseModel):
    concepts: list[ExtractedConcept] = Field(min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Practice loop. Student-facing models (…Out) must never carry the rubric,
# misconceptions, or the grader's covered/missed point text.
# ---------------------------------------------------------------------------
QuestionType = Literal["explain", "apply", "predict"]


class QuestionCreateIn(BaseModel):
    question_type: QuestionType | None = None


class QuestionOut(BaseModel):
    """Everything a student may see about a question: no rubric, no misconceptions."""

    id: int
    concept_id: int
    question_type: str
    prompt: str


class AttemptOut(BaseModel):
    id: int
    question_id: int
    status: str
    max_hint_level: int
    revealed: bool
    effective_score: float | None
    started_at: datetime
    completed_at: datetime | None


class AnswerIn(BaseModel):
    answer_text: str = Field(min_length=1, max_length=5000)

    @field_validator("answer_text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class AnswerOut(BaseModel):
    answer_id: int
    rubric_score: float
    feedback: str
    points_covered_count: int  # counts only: the text of the points stays on the server
    points_total: int
    attempt: AttemptOut


class HintOut(BaseModel):
    level: int
    hint_text: str
    cited_chunk_ids: list[int]
    hints_remaining: int
    attempt: AttemptOut


class RevealOut(BaseModel):
    explanation: str
    attempt: AttemptOut


class ConceptMasteryOut(BaseModel):
    concept_id: int
    name: str
    mastery: float
    attempt_count: int
    is_gap: bool


class IndependenceOut(BaseModel):
    completed_attempts: int
    independent_attempts: int
    independence_rate: float | None  # None until there is at least one completed attempt


# What we require from the model's JSON (validated before anything is stored).
class GeneratedQuestion(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    rubric: list[str] = Field(min_length=3, max_length=5)
    misconceptions: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, v: str) -> str:
        return v.strip()

    @field_validator("rubric", "misconceptions")
    @classmethod
    def clean_items(cls, v: list[str]) -> list[str]:
        items = [s.strip() for s in v if isinstance(s, str) and s.strip()]
        if len(items) != len(v):
            raise ValueError("entries must be non-empty strings")
        return items


class GradeResult(BaseModel):
    rubric_score: float = Field(ge=0, le=1)
    points_covered: list[str] = Field(default_factory=list)
    points_missed: list[str] = Field(default_factory=list)
    misconception: str | None = None
    feedback: str = Field(min_length=1)

    @field_validator("misconception")
    @classmethod
    def empty_is_none(cls, v: str | None) -> str | None:
        if v is None or v.strip().lower() in {"", "null", "none", "n/a"}:
            return None
        return v.strip()


# ---- Analytics (read from the pipeline's silver/gold tables) ----
class LearnerDayOut(BaseModel):
    day: date
    attempts_completed: int
    independence_rate: float
    avg_hint_level: float
    reveal_rate: float
    avg_effective_score: float | None


class ConceptSummaryOut(BaseModel):
    concept_id: int
    concept_name: str
    document_id: int
    attempts: int
    avg_effective_score: float | None
    avg_max_hint_level: float | None
    reveal_count: int
    mastery: float | None
    is_gap: bool
    top_misconception: str | None


class FunnelOut(BaseModel):
    document_id: int
    document_title: str | None
    concepts_extracted: int
    question_served: int
    answer_submitted: int
    completed: int
    revealed: int


class HeadlineOut(BaseModel):
    completed_attempts: int
    independent_attempts: int
    independence_rate: float | None
    avg_hint_level: float | None
    reveal_rate: float | None
    avg_effective_score: float | None
    gap_concepts: int


class AnalyticsOverviewOut(BaseModel):
    user_id: int
    display_name: str
    is_synthetic: bool
    pipeline_ready: bool  # False until `python -m pipeline.run` / POST /analytics/refresh ran
    headline: HeadlineOut
    learner_daily: list[LearnerDayOut]
    concept_summary: list[ConceptSummaryOut]
    funnel: list[FunnelOut]


class AnalyticsUserOut(BaseModel):
    id: int
    display_name: str
    is_synthetic: bool


class RefreshOut(BaseModel):
    tables: dict[str, int]
