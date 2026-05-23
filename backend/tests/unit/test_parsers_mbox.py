from pathlib import Path

from app.parsers.mbox import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "inbox.mbox"


def test_parse_mbox_emits_one_segment_per_message():
    pf = parse(file_id="f1", file_name="inbox.mbox", path=FIXTURE)
    assert pf.type == "mbox"
    assert len(pf.segments) >= 1
    loc = pf.segments[0].locator
    assert loc["type"] == "mbox"
    assert "msg-001" in loc["message_id"]
    assert "commercial liability" in pf.segments[0].text.lower()


def test_excerpt_returns_body_for_message_id():
    pf = parse(file_id="f1", file_name="inbox.mbox", path=FIXTURE)
    text = excerpt(pf, {"type": "mbox", "message_id": "<msg-001@acme.com>", "section": "body"})
    assert "quote" in text
