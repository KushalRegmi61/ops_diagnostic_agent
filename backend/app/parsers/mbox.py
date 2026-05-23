import mailbox
from pathlib import Path

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    mbox = mailbox.mbox(str(path))
    segments: list[ParsedSegment] = []
    try:
        for msg in mbox:
            msg_id = msg.get("Message-ID", "<unknown>")
            payload = msg.get_payload()
            if isinstance(payload, list):
                payload = "".join(p.get_payload() if hasattr(p, "get_payload") else str(p) for p in payload)
            body = payload if isinstance(payload, str) else str(payload)
            segments.append(ParsedSegment(
                text=body,
                locator={"type": "mbox", "message_id": msg_id, "section": "body"},
            ))
    finally:
        mbox.close()
    return ParsedFile(file_id=file_id, file_name=file_name, type="mbox", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    msg_id = locator["message_id"]
    section = locator.get("section", "body")
    for seg in parsed.segments:
        if seg.locator["message_id"] == msg_id and seg.locator["section"] == section:
            return seg.text
    raise ValueError(f"Message {msg_id} ({section}) not found")
