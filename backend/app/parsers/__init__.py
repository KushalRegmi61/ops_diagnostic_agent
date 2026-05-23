"""Parser registry. Each parser module exposes parse(*, file_id, file_name, path) and excerpt(parsed, locator)."""
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


def parse(file_id: str, file_name: str, path: Path, mime_type: str) -> ParsedFile:
    module_name = _MIME_ROUTES.get(mime_type)
    if module_name is None:
        raise ValueError(f"No parser registered for mime_type={mime_type}")
    mod = __import__(f"app.parsers.{module_name}", fromlist=["parse"])
    return mod.parse(file_id=file_id, file_name=file_name, path=path)
