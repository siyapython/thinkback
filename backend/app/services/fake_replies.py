"""Canned, deterministic replies used by FakeLLMClient (LLM_MODE=fake and all tests).

The fake looks at the `[task:...]` marker in the system prompt to decide what kind of reply to
build, then parses the labelled user prompt. It deliberately behaves like a simple but
well-behaved model, with one exception: a hint request whose student answer contains a
prompt-injection phrase makes it behave like a *compromised* model that leaks the rubric, so the
leak guardrail can be tested end to end.
"""

import json
import re

from app.prompts.extract_concepts import CHUNK_MARKER_RE
from app.services.leak import content_words

INJECTION_RE = re.compile(
    r"ignore (all |your |any )?(previous |prior )?instructions|give me the answer",
    re.IGNORECASE,
)
_TASK_RE = re.compile(r"\[task:(\w+)\]")


def _field(user: str, label: str, default: str = "") -> str:
    m = re.search(rf"^{re.escape(label)}: (.*)$", user, re.MULTILINE)
    return m.group(1).strip() if m else default


def _block(user: str, tag: str) -> str:
    m = re.search(rf"<{tag}>\n(.*?)\n</{tag}>", user, re.DOTALL)
    return m.group(1) if m else ""


def fake_reply(system: str, user: str) -> str:
    m = _TASK_RE.search(system)
    task = m.group(1) if m else "extract_concepts"
    return {
        "extract_concepts": _extract_concepts,
        "generate_question": _generate_question,
        "grade_answer": _grade_answer,
        "hint": _hint,
    }[task](system, user)


def _extract_concepts(system: str, user: str) -> str:
    indexes = [int(i) for i in CHUNK_MARKER_RE.findall(user)] or [0]
    concepts = [
        {
            "name": f"Concept {n}",
            "definition": f"Canned definition number {n}.",
            "chunk_indexes": [indexes[(n - 1) % len(indexes)]],
        }
        for n in range(1, 11)
    ]
    return json.dumps({"concepts": concepts})


_QUESTION_TEXT = {
    "explain": "In your own words, explain {name}.",
    "apply": "Describe how you would use {name} on a small practical problem, step by step.",
    "predict": "Predict what happens when {name} is applied to a simple case, and say why.",
}


def _generate_question(system: str, user: str) -> str:
    name = _field(user, "Concept", "the concept")
    qtype = _field(user, "Question type", "explain")
    return json.dumps(
        {
            "prompt": _QUESTION_TEXT[qtype].format(name=name),
            "rubric": [
                f"{name} depends on a matching condition between two inputs",
                "The output keeps only the entries that satisfy that condition",
                "Entries without a partner are dropped unless the variant says otherwise",
            ],
            "misconceptions": [
                "Believes the order of the inputs never matters",
                "Thinks every entry always appears in the output",
            ],
        }
    )


def _grade_answer(system: str, user: str) -> str:
    rubric = [
        re.sub(r"^\d+\. ", "", line) for line in _block(user, "rubric").splitlines() if line.strip()
    ]
    misconceptions = [
        line[2:] for line in _block(user, "known_misconceptions").splitlines() if line[:2] == "- "
    ]
    answer_words = content_words(_block(user, "student_answer"))
    covered, missed = [], []
    for point in rubric:
        words = content_words(point)
        hit = words and len(words & answer_words) / len(words) >= 0.5
        (covered if hit else missed).append(point)
    score = round(len(covered) / len(rubric), 2) if rubric else 0.0
    misconception = misconceptions[0] if misconceptions and score < 0.5 else None
    if score >= 0.8:
        feedback = "Nice work, you have the main ideas. Can you think of a case where it breaks?"
    else:
        feedback = "You are on a promising track. What else must be true for your answer to hold?"
    return json.dumps(
        {
            "rubric_score": score,
            "points_covered": covered,
            "points_missed": missed,
            "misconception": misconception,
            "feedback": feedback,
        }
    )


def _hint(system: str, user: str) -> str:
    level = int(_field(user, "Level", "1"))
    concept = _field(user, "Concept", "this concept")
    notes = _field(user, "Notes location", "your notes")
    answer = _block(user, "student_latest_answer")
    has_answer = bool(answer) and not answer.startswith("(the student has not")

    if INJECTION_RE.search(answer):
        # Simulates a model that fell for the injection: it dumps the confidential rubric.
        rubric_lines = user.split("CONFIDENTIAL rubric", 1)[1].split("\n", 1)[1]
        points = [ln[2:] for ln in rubric_lines.split("\n\n")[0].splitlines() if ln[:2] == "- "]
        return "Sure! The answer is: " + ". ".join(points) + "."

    if level == 1:
        return (
            f"What do you already know about {concept}, and what part of the question is unclear?"
        )
    if level == 2:
        return f"Take another look at {notes}. What does it say about how {concept} is set up?"
    if level == 3:
        if has_answer:
            return (
                f"Look again at the step in your answer where you describe {concept}: "
                "can you justify it from your notes?"
            )
        return f"Many students rush the first step of {concept}. What did you assume there?"
    return f"Fill in the blanks: with {concept}, first check ____, then do ____, so you get ____."
