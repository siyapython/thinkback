import hashlib

from sqlalchemy import select

from app.config import get_settings
from app.models import Chunk, Document, EventRaw
from tests.pdf_utils import make_pdf

TEXT = "SQL joins combine rows from two tables.\n\nA LEFT JOIN keeps unmatched left rows."


def post_text(client, title="Joins", text=TEXT):
    return client.post("/documents", json={"title": title, "text": text})


def post_pdf(client, data, filename="notes.pdf", title=None):
    form = {"title": title} if title else {}
    return client.post("/documents", files={"file": (filename, data, "application/pdf")}, data=form)


def test_upload_text(client, session):
    r = post_text(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "Joins"
    assert body["source_type"] == "text"
    assert body["status"] == "uploaded"
    assert body["chunk_count"] == 1
    assert "file_path" not in body and "content_hash" not in body
    doc = session.get(Document, body["id"])
    assert doc.content_hash == hashlib.sha256(TEXT.encode()).hexdigest()


def test_duplicate_is_rejected_with_409(client):
    assert post_text(client).status_code == 201
    r = post_text(client, title="A different title, same content")
    assert r.status_code == 409
    assert "already uploaded" in r.json()["detail"]


def test_blank_and_missing_fields_rejected(client):
    assert client.post("/documents", json={"title": "x", "text": "   "}).status_code == 422
    assert client.post("/documents", json={"text": "hi"}).status_code == 422
    assert (
        client.post("/documents", content=b"x", headers={"content-type": "text/plain"}).status_code
        == 415
    )


def test_oversized_text_rejected_with_413(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_BYTES", 1000)
    r = post_text(client, text="a" * 5000)
    assert r.status_code == 413
    assert "too large" in r.json()["detail"]


def test_oversized_pdf_rejected_with_413(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_BYTES", 1000)
    r = post_pdf(client, make_pdf(["x" * 3000]))
    assert r.status_code == 413


def test_upload_pdf_records_pages_and_hides_file_path(client, session):
    pdf = make_pdf(["Page one about SELECT.", "Page two about WHERE.", "Page three about JOIN."])
    r = post_pdf(client, pdf)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source_type"] == "pdf"
    assert body["page_count"] == 3
    assert body["title"] == "notes"  # from the filename
    assert body["original_filename"] == "notes.pdf"
    assert body["chunk_count"] >= 1
    assert "file_path" not in body
    chunk = session.scalars(select(Chunk).where(Chunk.document_id == body["id"])).first()
    assert (chunk.page_start, chunk.page_end) == (1, 3)
    assert "Page one" in chunk.text and "Page three" in chunk.text
    saved = list(get_settings().UPLOAD_DIR.glob("*.pdf"))
    assert len(saved) == 1 and saved[0].read_bytes() == pdf


def test_pdf_filename_cannot_escape_upload_dir(client):
    r = post_pdf(client, make_pdf(["hello world"]), filename="../../evil.pdf")
    assert r.status_code == 201
    assert r.json()["original_filename"] == "evil.pdf"
    assert all(p.parent == get_settings().UPLOAD_DIR for p in get_settings().UPLOAD_DIR.glob("*"))


def test_pdf_without_text_is_marked_failed(client):
    r = post_pdf(client, make_pdf(["", ""]))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed"
    assert "scanned images" in body["error_message"]
    assert body["chunk_count"] == 0
    assert client.post(f"/documents/{body['id']}/extract-concepts").status_code == 422


def test_pdf_over_page_limit_rejected(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "MAX_PAGES", 2)
    r = post_pdf(client, make_pdf(["a", "b", "c"]))
    assert r.status_code == 422
    assert "limit is 2" in r.json()["detail"]


def test_not_a_pdf_rejected(client):
    assert post_pdf(client, b"just some text").status_code == 422
    assert post_pdf(client, b"%PDF-1.4 garbage").status_code == 422


def test_duplicate_pdf_rejected(client):
    pdf = make_pdf(["same"])
    assert post_pdf(client, pdf).status_code == 201
    assert post_pdf(client, pdf, filename="other.pdf").status_code == 409


def test_list_and_get(client):
    a = post_text(client, "A", "first doc").json()["id"]
    b = post_text(client, "B", "second doc").json()["id"]
    listing = client.get("/documents").json()
    assert [d["id"] for d in listing] == [b, a]
    assert all("chunk_count" in d and "file_path" not in d for d in listing)
    one = client.get(f"/documents/{a}")
    assert one.status_code == 200 and one.json()["title"] == "A"
    assert client.get("/documents/999999999").status_code == 404


def test_upload_writes_document_uploaded_event(client, session, user):
    doc_id = post_text(client).json()["id"]
    event = session.scalars(
        select(EventRaw).where(EventRaw.event_type == "document_uploaded")
    ).one()
    assert event.user_id == user.id and event.document_id == doc_id
    assert event.payload["source_type"] == "text"
    assert event.payload["chunk_count"] == 1
    assert event.payload["status"] == "uploaded"
