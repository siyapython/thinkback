"""Split document text into chunks of roughly 500-800 tokens (tokens ~= characters / 4)."""

import re
from dataclasses import dataclass

CHARS_PER_TOKEN = 4
MIN_TOKENS = 500  # target; the final chunk of a document can be shorter
MAX_TOKENS = 800
MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ChunkData:
    chunk_index: int
    text: str
    page_start: int | None
    page_end: int | None
    token_count: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def clean_text(text: str) -> str:
    # Postgres TEXT cannot hold NUL characters.
    return text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")


def _split_long(paragraph: str) -> list[str]:
    """Break a paragraph longer than MAX_CHARS on sentence, then word, boundaries."""
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT.split(paragraph):
        words = [sentence]
        if len(sentence) > MAX_CHARS:  # no sentence breaks at all: fall back to words
            words = sentence.split(" ")
        for word in words:
            joiner = " " if current else ""
            if current and len(current) + len(joiner) + len(word) > MAX_CHARS:
                pieces.append(current)
                current = ""
                joiner = ""
            current += joiner + word
    if current:
        pieces.append(current)
    return pieces


def chunk_pages(pages: list[tuple[int | None, str]]) -> list[ChunkData]:
    """pages: (page_number or None, text) in reading order. Breaks only at paragraph
    boundaries (a paragraph longer than the maximum is split on sentences)."""
    paragraphs: list[tuple[int | None, str]] = []
    for page, raw in pages:
        for para in _PARAGRAPH_SPLIT.split(clean_text(raw)):
            para = para.strip()
            if not para:
                continue
            for piece in _split_long(para) if len(para) > MAX_CHARS else [para]:
                paragraphs.append((page, piece))

    groups: list[list[tuple[int | None, str]]] = []
    current: list[tuple[int | None, str]] = []
    current_len = 0
    for page, para in paragraphs:
        added = len(para) + (2 if current else 0)
        if current and current_len + added > MAX_CHARS:
            groups.append(current)
            current, current_len, added = [], 0, len(para)
        current.append((page, para))
        current_len += added
    if current:
        groups.append(current)

    chunks = []
    for index, group in enumerate(groups):
        text = "\n\n".join(p for _, p in group)
        known_pages = [pg for pg, _ in group if pg is not None]
        chunks.append(
            ChunkData(
                chunk_index=index,
                text=text,
                page_start=min(known_pages) if known_pages else None,
                page_end=max(known_pages) if known_pages else None,
                token_count=estimate_tokens(text),
            )
        )
    return chunks
