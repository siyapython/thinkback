import re


def neutralize_tags(text: str, tag_names: tuple[str, ...]) -> str:
    """Stop untrusted text from closing/opening one of our delimiter tags (e.g. by writing
    '</student_answer> New instructions: ...'). Other angle brackets (like SQL `a < b`) stay."""
    names = "|".join(re.escape(t) for t in tag_names)
    return re.sub(rf"<\s*/?\s*(?:{names})\s*/?\s*>", "[tag removed]", text, flags=re.IGNORECASE)


STUDENT_TAGS = (
    "student_answer",
    "student_latest_answer",
    "question",
    "rubric",
    "known_misconceptions",
    "source_material",
)


def wrap_student_text(text: str) -> str:
    return neutralize_tags(text, STUDENT_TAGS)
