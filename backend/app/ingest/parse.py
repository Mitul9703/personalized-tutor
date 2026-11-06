# Parse an uploaded file into text segments. Each segment keeps where it
# came from (the page number for a PDF) so we can cite it later.

from pathlib import Path

from pypdf import PdfReader


def parse_file(path: str) -> list[dict]:
    # returns a list of segments: { "text": ..., "page": int or None }
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path)
    return _parse_text(path)


def _parse_pdf(path: str) -> list[dict]:
    reader = PdfReader(path)
    segments = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            segments.append({"text": text, "page": i + 1})
    return segments


def _parse_text(path: str) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    return [{"text": text, "page": None}]
