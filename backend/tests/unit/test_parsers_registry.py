"""Parser registry dispatch: mime_type maps to the right parser implementation."""
from pathlib import Path

import pytest

from app.parsers import parse

FIX = Path(__file__).parent.parent / "fixtures"


@pytest.mark.parametrize(
    "file_name,mime_type,expected_type",
    [
        ("sop.pdf", "application/pdf", "pdf"),
        ("sop.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
        ("notes.md", "text/markdown", "md"),
        ("notes.txt", "text/plain", "txt"),
        ("call.vtt", "text/vtt", "transcript_vtt"),
        ("call.srt", "application/x-subrip", "transcript_srt"),
        ("leads.csv", "text/csv", "csv"),
        ("leads.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
        ("inbox.mbox", "application/mbox", "mbox"),
        ("crm.json", "application/json", "json"),
    ],
)
def test_registry_routes_to_correct_parser(file_name, mime_type, expected_type):
    """For each supported mime, the registry routes to the parser that tags ParsedFile.type."""
    pf = parse(file_id="f1", file_name=file_name, path=FIX / file_name, mime_type=mime_type)
    assert pf.type == expected_type
    assert len(pf.segments) > 0


def test_registry_raises_on_unknown_mime():
    """Unknown mime types raise ValueError("No parser registered ...")."""
    with pytest.raises(ValueError, match="No parser registered"):
        parse(file_id="f1", file_name="x.bin", path=FIX / "sop.pdf", mime_type="application/octet-stream")
