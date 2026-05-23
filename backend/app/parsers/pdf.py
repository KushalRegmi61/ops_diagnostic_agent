from pathlib import Path

import fitz

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    doc = fitz.open(path)
    segments: list[ParsedSegment] = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        segments.append(ParsedSegment(
            text=text,
            locator={"type": "pdf", "page": page_num, "span_start": 0, "span_end": len(text)},
        ))
    doc.close()
    return ParsedFile(file_id=file_id, file_name=file_name, type="pdf", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    page = locator["page"]
    span_start = locator["span_start"]
    span_end = locator["span_end"]
    for seg in parsed.segments:
        if seg.locator["page"] == page:
            return seg.text[span_start:span_end]
    raise ValueError(f"Page {page} not found in parsed file")
