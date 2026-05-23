from pathlib import Path

from docx import Document

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
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
    idx = locator["paragraph_index"]
    span_start = locator["span_start"]
    span_end = locator["span_end"]
    for seg in parsed.segments:
        if seg.locator["paragraph_index"] == idx:
            return seg.text[span_start:span_end]
    raise ValueError(f"Paragraph {idx} not found")
