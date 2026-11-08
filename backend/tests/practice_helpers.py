import json

from app.models import Question
from tests.pdf_utils import make_pdf

NOTES = "\n\n".join(
    f"Paragraph {i}. Joins combine rows from two tables using a matching condition. " * 30
    for i in range(6)
)


def upload_and_extract(client, text: str = NOTES) -> dict:
    doc = client.post("/documents", json={"title": "My notes", "text": text}).json()
    extracted = client.post(f"/documents/{doc['id']}/extract-concepts").json()
    return {"document_id": doc["id"], "concepts": extracted["concepts"]}


def upload_pdf_and_extract(client) -> dict:
    pdf = make_pdf(["Page one is about joins.", "Page two is about keys.", "Page three: nulls."])
    doc = client.post(
        "/documents", files={"file": ("n.pdf", pdf, "application/pdf")}, data={"title": "PDF notes"}
    ).json()
    extracted = client.post(f"/documents/{doc['id']}/extract-concepts").json()
    return {"document_id": doc["id"], "concepts": extracted["concepts"]}


def make_question(client, concept_id: int, question_type: str | None = None) -> dict:
    body = {"question_type": question_type} if question_type else None
    r = client.post(f"/concepts/{concept_id}/questions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def start_attempt(client, question_id: int) -> dict:
    r = client.post(f"/questions/{question_id}/attempts")
    assert r.status_code == 201, r.text
    return r.json()


def setup_attempt(client, concept_index: int = 0) -> dict:
    """Upload, extract, create a question and start an attempt."""
    info = upload_and_extract(client)
    concept = info["concepts"][concept_index]
    question = make_question(client, concept["id"])
    attempt = start_attempt(client, question["id"])
    return {
        **info,
        "concept_id": concept["id"],
        "question_id": question["id"],
        "attempt_id": attempt["id"],
    }


def rubric_of(session, question_id: int) -> list[str]:
    return list(session.get(Question, question_id).rubric)


def good_answer(session, question_id: int) -> str:
    return " ".join(rubric_of(session, question_id))


def grade_json(score: float, *, covered=(), missed=(), misconception=None, feedback="Hmm, why?"):
    return json.dumps(
        {
            "rubric_score": score,
            "points_covered": list(covered),
            "points_missed": list(missed),
            "misconception": misconception,
            "feedback": feedback,
        }
    )


def answer(client, attempt_id: int, text: str):
    return client.post(f"/attempts/{attempt_id}/answers", json={"answer_text": text})
