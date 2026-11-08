"""SQLAlchemy 2.0 models. Enums are TEXT + CHECK constraints (see docs/LEARNING.md)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _pk() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(), primary_key=True)


def _ts_now() -> Mapped[datetime]:
    return mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)


def _ts_null() -> Mapped[datetime | None]:
    return mapped_column(TIMESTAMP(timezone=True), nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = _pk()
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _ts_now()


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("source_type IN ('pdf', 'text')", name="source_type"),
        CheckConstraint("status IN ('uploaded', 'processing', 'ready', 'failed')", name="status"),
        UniqueConstraint("user_id", "content_hash", name="uq_documents_user_id_content_hash"),
    )

    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="uploaded", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", passive_deletes=True)
    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="document", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_id_chunk_index"),
    )

    id: Mapped[int] = _pk()
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (
        CheckConstraint("origin IN ('model', 'user')", name="origin"),
        UniqueConstraint("document_id", "name", name="uq_concepts_document_id_name"),
    )

    id: Mapped[int] = _pk()
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    # Deliberate simplification: an array of chunk ids instead of a join table.
    source_chunk_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BigInteger), server_default=text("'{}'"), nullable=False
    )
    origin: Mapped[str] = mapped_column(Text, server_default="model", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()

    document: Mapped[Document] = relationship(back_populates="concepts")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="concept", passive_deletes=True
    )


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("question_type IN ('explain', 'apply', 'predict')", name="question_type"),
    )

    id: Mapped[int] = _pk()
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    question_type: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    rubric: Mapped[Any] = mapped_column(JSONB, nullable=False)
    misconceptions: Mapped[Any | None] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _ts_now()

    concept: Mapped[Concept] = relationship(back_populates="questions")


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        CheckConstraint("status IN ('in_progress', 'completed', 'abandoned')", name="status"),
        CheckConstraint("max_hint_level BETWEEN 0 AND 4", name="max_hint_level"),
        CheckConstraint("effective_score BETWEEN 0 AND 1", name="effective_score"),
    )

    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="in_progress", nullable=False)
    max_hint_level: Mapped[int] = mapped_column(SmallInteger, server_default="0", nullable=False)
    revealed_at: Mapped[datetime | None] = _ts_null()
    effective_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    started_at: Mapped[datetime] = _ts_now()
    completed_at: Mapped[datetime | None] = _ts_null()

    answers: Mapped[list["Answer"]] = relationship(back_populates="attempt", passive_deletes=True)
    hints: Mapped[list["HintRequest"]] = relationship(
        back_populates="attempt", passive_deletes=True
    )


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (CheckConstraint("rubric_score BETWEEN 0 AND 1", name="rubric_score"),)

    id: Mapped[int] = _pk()
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False
    )
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    points_covered: Mapped[Any | None] = mapped_column(JSONB)
    points_missed: Mapped[Any | None] = mapped_column(JSONB)
    misconception: Mapped[str | None] = mapped_column(Text)
    feedback: Mapped[str | None] = mapped_column(Text)
    grader_model: Mapped[str | None] = mapped_column(Text)
    grader_prompt_version: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = _ts_now()
    graded_at: Mapped[datetime | None] = _ts_null()

    attempt: Mapped[Attempt] = relationship(back_populates="answers")


class HintRequest(Base):
    __tablename__ = "hint_requests"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 4", name="level"),
        UniqueConstraint("attempt_id", "level", name="uq_hint_requests_attempt_id_level"),
    )

    id: Mapped[int] = _pk()
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hint_text: Mapped[str] = mapped_column(Text, nullable=False)
    cited_chunk_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    leak_check_passed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    regenerated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _ts_now()

    attempt: Mapped[Attempt] = relationship(back_populates="hints")


class ConceptMastery(Base):
    __tablename__ = "concept_mastery"
    __table_args__ = (CheckConstraint("mastery BETWEEN 0 AND 1", name="mastery"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True
    )
    mastery: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default="0", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    last_misconception: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = _ts_now()


EVENT_TYPES = (
    "document_uploaded",
    "concepts_extracted",
    "question_served",
    "hint_requested",
    "answer_submitted",
    "answer_graded",
    "answer_revealed",
)


class EventRaw(Base):
    """Append-only event log. Deliberately NO foreign keys (see docs/LEARNING.md)."""

    __tablename__ = "events_raw"
    __table_args__ = (
        CheckConstraint(
            "event_type IN (" + ", ".join(f"'{e}'" for e in EVENT_TYPES) + ")",
            name="event_type",
        ),
        Index("ix_events_raw_user_id_occurred_at", "user_id", "occurred_at"),
        Index("ix_events_raw_event_type_occurred_at", "event_type", "occurred_at"),
    )

    id: Mapped[int] = _pk()
    # user_id is the one FK the spec asks for on events_raw.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[int | None] = mapped_column(BigInteger)
    concept_id: Mapped[int | None] = mapped_column(BigInteger)
    question_id: Mapped[int | None] = mapped_column(BigInteger)
    attempt_id: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[Any] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    schema_version: Mapped[int] = mapped_column(SmallInteger, server_default="1", nullable=False)
    occurred_at: Mapped[datetime] = _ts_now()
