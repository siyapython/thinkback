from datetime import datetime

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
