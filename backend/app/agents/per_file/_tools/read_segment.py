from app.schemas import ParsedFile


def read_segment(parsed: ParsedFile, *, segment_index: int) -> dict:
    if segment_index < 0 or segment_index >= len(parsed.segments):
        raise ValueError(f"segment_index {segment_index} out of range")
    seg = parsed.segments[segment_index]
    return {"text": seg.text, "locator": seg.locator}
