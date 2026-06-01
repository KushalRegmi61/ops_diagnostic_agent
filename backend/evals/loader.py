"""Load the eval corpus manifest into typed cases and parse each input file.

Bridges ``corpus/manifest.json`` to ``app.parsers`` so the scorecard can run the
real per-file agent over real parsed inputs. Pure I/O + dispatch; no LLM.
"""
import json
from pathlib import Path

from pydantic import BaseModel

from app.parsers import parse as parse_file
from app.schemas import ParsedFile

_ROOT = Path(__file__).parent / "corpus"
_FILES = _ROOT / "files"

_MIME_BY_TYPE = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown",
    "txt": "text/plain",
    "vtt": "text/vtt",
    "srt": "application/x-subrip",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "mbox": "application/mbox",
    "json": "application/json",
}


class CorpusCase(BaseModel):
    """One expected-floor eval case from the manifest."""

    file: str
    type: str
    min_workflows: int = 0
    min_pain_signals: int = 0
    min_lead_rows: int = 0
    min_citations: int = 0
    must_converge: bool = True


def load_cases() -> list[CorpusCase]:
    """Read manifest.json into validated CorpusCase objects."""
    raw = json.loads((_ROOT / "manifest.json").read_text())
    return [CorpusCase(**entry) for entry in raw]


def parse_case(case: CorpusCase) -> ParsedFile:
    """Parse a corpus file into a ParsedFile via the registered parser (routes by mime)."""
    mime = _MIME_BY_TYPE.get(case.type)
    if mime is None:
        raise ValueError(f"No mime mapping for corpus type={case.type}")
    return parse_file(
        file_id=f"eval_{case.file}",
        file_name=case.file,
        path=_FILES / case.file,
        mime_type=mime,
    )
