import io

from fastapi import HTTPException
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.services.chunking import clean_text


def extract_pdf_pages(data: bytes, max_pages: int) -> list[str]:
    """Return the text of each page. Raises HTTP 422 for unreadable or too-long PDFs."""
    if not data.startswith(b"%PDF-"):
        raise HTTPException(422, "That file is not a PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise HTTPException(422, "Password-protected PDFs are not supported.")
        if len(reader.pages) > max_pages:
            raise HTTPException(
                422, f"PDF has {len(reader.pages)} pages; the limit is {max_pages}."
            )
        return [clean_text(page.extract_text() or "") for page in reader.pages]
    except (PyPdfError, ValueError, KeyError, RecursionError) as exc:
        raise HTTPException(422, "Could not read that PDF; it may be corrupted.") from exc
