"""DOCX parser. One ParsedSegment per paragraph; the locator carries
``paragraph_index`` and the byte span within the paragraph text.
"""
from pathlib import Path

from docx import Document

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    """Open the DOCX at ``path`` and emit one segment per paragraph with a ``docx`` locator."""
    doc = Document(str(path))
    segments: list[ParsedSegment] = []
    for idx, para in enumerate(doc.paragraphs):
        text = para.text
        segments.append(ParsedSegment(
            text=text,
            locator={"type": "docx", "paragraph_index": idx, "span_start": 0, "span_end": len(text)},
        ))
    return ParsedFile(file_id=file_id, file_name=file_name, type="docx", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    """Return the byte-span slice of the paragraph identified by ``locator['paragraph_index']``."""
    idx = locator["paragraph_index"]
    span_start = locator["span_start"]
    span_end = locator["span_end"]
    for seg in parsed.segments:
        if seg.locator["paragraph_index"] == idx:
            return seg.text[span_start:span_end]
    raise ValueError(f"Paragraph {idx} not found")
