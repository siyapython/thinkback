import json

from sqlalchemy import select

from app.models import Chunk, Concept, Document, EventRaw
from app.prompts.extract_concepts import PROMPT_VERSION
from tests.test_documents import post_text

LONG_TEXT = "\n\n".join(f"Paragraph {i}. " + "SQL is declarative. " * 120 for i in range(8))


def make_doc(client, text=LONG_TEXT) -> int:
    r = post_text(client, text=text)
    assert r.status_code == 201
    return r.json()["id"]


def script(*concepts) -> list[str]:
    return [json.dumps({"concepts": list(concepts)})]


def c(name, indexes, definition="A definition."):
    return {"name": name, "definition": definition, "chunk_indexes": indexes}


def test_extraction_stores_concepts_with_valid_chunk_ids(client, session):
    doc_id = make_doc(client)
    r = client.post(f"/documents/{doc_id}/extract-concepts")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document"]["status"] == "ready"
    assert body["created"] == 10 and body["updated"] == 0
    assert body["model"] == "fake-llm-v1" and body["prompt_version"] == PROMPT_VERSION

    chunk_ids = set(session.scalars(select(Chunk.id).where(Chunk.document_id == doc_id)))
    assert len(chunk_ids) > 1
    concepts = session.scalars(select(Concept).where(Concept.document_id == doc_id)).all()
    assert len(concepts) == 10
    for concept in concepts:
        assert concept.source_chunk_ids and set(concept.source_chunk_ids) <= chunk_ids
        assert concept.model == "fake-llm-v1"
        assert concept.prompt_version == PROMPT_VERSION
        assert concept.origin == "model" and concept.is_active

    listed = client.get(f"/documents/{doc_id}/concepts").json()
    assert [x["name"] for x in listed] == [x.name for x in sorted(concepts, key=lambda x: x.id)]


def test_prompt_tells_model_to_use_only_the_material(client, llm):
    client.post(f"/documents/{make_doc(client)}/extract-concepts")
    assert "ONLY the material" in llm.calls[0]["system"]
    assert "[chunk 0]" in llm.calls[0]["user"]


def test_rerun_is_idempotent(client, session):
    doc_id = make_doc(client)
    first = client.post(f"/documents/{doc_id}/extract-concepts").json()
    ids_before = sorted(x["id"] for x in first["concepts"])
    second = client.post(f"/documents/{doc_id}/extract-concepts").json()
    assert second["created"] == 0 and second["updated"] == 10
    assert sorted(x["id"] for x in second["concepts"]) == ids_before
    count = len(session.scalars(select(Concept).where(Concept.document_id == doc_id)).all())
    assert count == 10


def test_rerun_does_not_overwrite_user_concepts(client, session):
    doc_id = make_doc(client)
    client.post(f"/documents/{doc_id}/extract-concepts")
    mine = Concept(document_id=doc_id, name="concept 1", definition="mine", origin="user")
    existing = session.scalars(select(Concept).where(Concept.name == "Concept 1")).one()
    session.delete(existing)
    session.add(mine)
    session.commit()
    client.post(f"/documents/{doc_id}/extract-concepts")
    session.expire_all()
    assert session.get(Concept, mine.id).definition == "mine"
    assert len(session.scalars(select(Concept).where(Concept.document_id == doc_id)).all()) == 10


def test_dedupes_by_normalized_name_and_drops_bad_indexes(client, session, llm):
    llm._script = script(
        c("Left Join", [0]),
        c("  left-join ", [0]),  # same after normalizing
        c("Primary Key", [0, 99]),  # 99 does not exist: ignored
        c("Ghost", [99]),  # no valid chunk: dropped
        c("Empty", []),  # no chunk: dropped
    )
    doc_id = make_doc(client)
    body = client.post(f"/documents/{doc_id}/extract-concepts").json()
    assert sorted(x["name"] for x in body["concepts"]) == ["Left Join", "Primary Key"]
    pk = next(x for x in body["concepts"] if x["name"] == "Primary Key")
    first_chunk = session.scalars(
        select(Chunk.id).where(Chunk.document_id == doc_id, Chunk.chunk_index == 0)
    ).one()
    assert pk["source_chunk_ids"] == [first_chunk]


def test_caps_at_25_concepts(client, llm):
    llm._script = script(*[c(f"Topic {i}", [0]) for i in range(40)])
    body = client.post(f"/documents/{make_doc(client)}/extract-concepts").json()
    assert len(body["concepts"]) == 25


def test_malformed_json_is_retried_once(client, llm):
    llm._script = ["this is not json"] + script(c("Index", [0]))
    r = client.post(f"/documents/{make_doc(client)}/extract-concepts")
    assert r.status_code == 200 and len(llm.calls) == 2


def test_malformed_twice_fails_document_with_clear_error(client, session, llm):
    llm._script = ["nope", "still nope"]
    doc_id = make_doc(client)
    r = client.post(f"/documents/{doc_id}/extract-concepts")
    assert r.status_code == 502
    assert "malformed JSON" in r.json()["detail"]
    doc = session.get(Document, doc_id)
    assert doc.status == "failed" and "malformed JSON" in doc.error_message
    assert session.scalars(select(Concept).where(Concept.document_id == doc_id)).all() == []
    event = session.scalars(
        select(EventRaw).where(EventRaw.event_type == "concepts_extracted")
    ).one()
    assert event.payload["success"] is False


def test_failed_document_can_be_retried_successfully(client, session, llm):
    llm._script = ["bad", "bad"]
    doc_id = make_doc(client)
    assert client.post(f"/documents/{doc_id}/extract-concepts").status_code == 502
    llm._script = None
    assert client.post(f"/documents/{doc_id}/extract-concepts").status_code == 200
    session.expire_all()
    doc = session.get(Document, doc_id)
    assert doc.status == "ready" and doc.error_message is None


def test_no_usable_concepts_fails(client, session, llm):
    llm._script = script(c("Ghost", [42]))
    doc_id = make_doc(client)
    assert client.post(f"/documents/{doc_id}/extract-concepts").status_code == 502
    assert session.get(Document, doc_id).status == "failed"


def test_events_written_for_extraction(client, session, user):
    doc_id = make_doc(client)
    client.post(f"/documents/{doc_id}/extract-concepts")
    client.post(f"/documents/{doc_id}/extract-concepts")
    events = session.scalars(
        select(EventRaw).where(EventRaw.event_type == "concepts_extracted").order_by(EventRaw.id)
    ).all()
    assert len(events) == 2
    first, second = (e.payload for e in events)
    assert events[0].user_id == user.id and events[0].document_id == doc_id
    assert first == {
        "success": True,
        "concept_count": 10,
        "created": 10,
        "updated": 0,
        "chunk_count": first["chunk_count"],
        "model": "fake-llm-v1",
        "prompt_version": PROMPT_VERSION,
    }
    assert second["created"] == 0 and second["updated"] == 10


def test_unknown_document_404(client):
    assert client.post("/documents/999999999/extract-concepts").status_code == 404
    assert client.get("/documents/999999999/concepts").status_code == 404


def test_too_long_document_is_refused(client, session, monkeypatch):
    from app.config import get_settings

    doc_id = make_doc(client)
    monkeypatch.setattr(get_settings(), "MAX_EXTRACTION_CHARS", 100)
    r = client.post(f"/documents/{doc_id}/extract-concepts")
    assert r.status_code == 422 and "too long" in r.json()["detail"]


def test_fake_default_works_with_tiny_doc(client):
    doc_id = make_doc(client, text="Just one short paragraph.")
    body = client.post(f"/documents/{doc_id}/extract-concepts").json()
    assert len(body["concepts"]) == 10  # all point at the single chunk
