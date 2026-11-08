"""Leak guardrail: does a piece of text give away too much of the confidential rubric?

Idea: reduce the text and each rubric key point to their meaningful words, then measure how much
of a key point's vocabulary shows up in the text. A hint that repeats most of a key point's
words (or a large share of the whole rubric's words) is probably telling, not nudging.
Words that already appear in the question are ignored: repeating the question is not a leak.
"""

import re
from dataclasses import dataclass

POINT_THRESHOLD = 0.6  # share of ONE key point's words that may appear in the text
RUBRIC_THRESHOLD = 0.5  # share of the WHOLE rubric's words that may appear in the text
MIN_VERBATIM_CHARS = 25  # a key point this long appearing word for word is always a leak

STOPWORDS = frozenset(
    """the and for are but not you your with that this from have has had was were will would can
    could should may might must been being its their there then than them they these those into
    onto out over under about above below between each other some such only own same too very
    just also how what when where which who whom why all any both few more most nor off once
    here does did doing done get got make made use used using""".split()
)

_WORD = re.compile(r"[a-z0-9_]+")


def _stem(word: str) -> str:
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def content_words(text: str) -> set[str]:
    """The set of meaningful (stemmed, non-stopword) words in `text`."""
    words = (_stem(w) for w in _WORD.findall(text.lower()))
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}


def _normalize(text: str) -> str:
    return " ".join(_WORD.findall(text.lower()))


@dataclass(frozen=True)
class LeakResult:
    leaked: bool
    reason: str = ""
    point_overlap: float = 0.0  # highest share of any single key point found in the text
    rubric_overlap: float = 0.0  # share of the whole rubric's words found in the text


def check_leak(
    text: str,
    rubric_points: list[str],
    *,
    exclude: str = "",
    point_threshold: float = POINT_THRESHOLD,
    rubric_threshold: float = RUBRIC_THRESHOLD,
) -> LeakResult:
    """Decide whether `text` covers too much of the rubric.

    `exclude` is text (usually the question) whose words are ignored.
    """
    text_words = content_words(text)
    text_norm = _normalize(text)
    ignored = content_words(exclude)

    best_point = 0.0
    all_words: set[str] = set()
    verbatim = False
    for point in rubric_points:
        norm = _normalize(point)
        if len(norm) >= MIN_VERBATIM_CHARS and norm in text_norm:
            verbatim = True
        words = content_words(point) - ignored
        if not words:
            continue
        all_words |= words
        best_point = max(best_point, len(words & text_words) / len(words))
    rubric_overlap = len(all_words & text_words) / len(all_words) if all_words else 0.0

    if verbatim:
        return LeakResult(True, "repeats a rubric key point verbatim", best_point, rubric_overlap)
    if best_point >= point_threshold:
        return LeakResult(True, "covers most of one rubric key point", best_point, rubric_overlap)
    if rubric_overlap >= rubric_threshold:
        return LeakResult(True, "covers much of the whole rubric", best_point, rubric_overlap)
    return LeakResult(False, "", best_point, rubric_overlap)


def hint_shape_ok(text: str, *, max_chars: int = 700) -> bool:
    """A hint must be non-empty, short, and contain at most one question."""
    return bool(text.strip()) and len(text) <= max_chars and text.count("?") <= 1
