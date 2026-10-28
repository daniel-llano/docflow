"""Turns an uploaded file into plain text."""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

TEXT_TYPES = {".txt", ".md", ".csv", ".log"}
ALLOWED = TEXT_TYPES | {".pdf"}
MAX_TEXT_CHARS = 200_000


class UnreadableDocument(ValueError):
    pass


def extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot >= 0 else ""


def read_text(filename: str, data: bytes) -> str:
    ext = extension(filename)
    if ext not in ALLOWED:
        raise UnreadableDocument(f"Upload a {', '.join(sorted(ALLOWED))} file.")

    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except (PdfReadError, ValueError) as ex:
            raise UnreadableDocument("That PDF couldn't be read.") from ex
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")

    text = text.strip()
    if not text:
        raise UnreadableDocument("The file has no readable text. Scanned PDFs need OCR first.")
    return text[:MAX_TEXT_CHARS]
