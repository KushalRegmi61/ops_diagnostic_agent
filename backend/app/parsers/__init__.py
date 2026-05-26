"""Parser registry and shared dispatch entry points.

Each parser module under ``app.parsers`` exposes a ``parse(*, file_id, file_name, path)``
that produces a ``ParsedFile`` of typed segments, and an ``excerpt(parsed, locator)``
that round-trips a Source locator back to its original text. This module routes by
MIME type for ``parse`` and by ``ParsedFile.type`` for ``excerpt`` so the rest of the
system (citation validator, /api/files/{id}/excerpt endpoint, self_review_final)
can treat every file family uniformly.
"""
from pathlib import Path

from app.schemas import ParsedFile

_MIME_ROUTES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/markdown": "md",
    "text/plain": "txt",
    "text/vtt": "vtt",
    "application/x-subrip": "srt",
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/mbox": "mbox",
    "application/json": "json",
}

# FileType (as set by parsers) -> excerpt module name. Keeps in sync with schemas.FileType.
_EXCERPT_ROUTES = {
    "pdf": "pdf",
    "docx": "docx",
    "md": "md",
    "txt": "txt",
    "transcript_vtt": "vtt",
    "transcript_srt": "srt",
    "csv": "csv",
    "xlsx": "xlsx",
    "mbox": "mbox",
    "json": "json",
}


def parse(file_id: str, file_name: str, path: Path, mime_type: str) -> ParsedFile:
    """Dispatch to the parser module registered for ``mime_type`` and return a ParsedFile."""
    module_name = _MIME_ROUTES.get(mime_type)
    if module_name is None:
        raise ValueError(f"No parser registered for mime_type={mime_type}")
    mod = __import__(f"app.parsers.{module_name}", fromlist=["parse"])
    return mod.parse(file_id=file_id, file_name=file_name, path=path)


def excerpt(parsed: ParsedFile, locator) -> str:
    """Dispatch to the ``excerpt()`` of the parser module matching ``parsed.type``; accepts a dict or a locator model."""
    module_name = _EXCERPT_ROUTES.get(parsed.type)
    if module_name is None:
        raise ValueError(f"No excerpt module for parsed.type={parsed.type}")
    mod = __import__(f"app.parsers.{module_name}", fromlist=["excerpt"])
    loc_dict = locator.model_dump() if hasattr(locator, "model_dump") else locator
    return mod.excerpt(parsed, loc_dict)
