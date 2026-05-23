from pathlib import Path

import pandas as pd

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    df = pd.read_csv(path)
    segments: list[ParsedSegment] = []
    for idx, row in df.iterrows():
        text = " | ".join(f"{c}={row[c]}" for c in df.columns)
        segments.append(ParsedSegment(
            text=text,
            locator={"type": "table", "row_index": int(idx)},
        ))
    return ParsedFile(file_id=file_id, file_name=file_name, type="csv", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    idx = locator["row_index"]
    for seg in parsed.segments:
        if seg.locator["row_index"] == idx:
            return seg.text
    raise ValueError(f"Row {idx} not found")
