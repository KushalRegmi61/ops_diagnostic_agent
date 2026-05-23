from pathlib import Path

from app.parsers.vtt import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "call.vtt"


def test_parse_vtt_emits_cues_with_timestamps():
    pf = parse(file_id="f1", file_name="call.vtt", path=FIXTURE)
    assert pf.type == "transcript_vtt"
    assert len(pf.segments) == 2
    loc0 = pf.segments[0].locator
    assert loc0["type"] == "transcript"
    assert loc0["ts_start"] == "00:00:01.000"
    assert "lead response time" in pf.segments[0].text


def test_excerpt_returns_cue_text():
    pf = parse(file_id="f1", file_name="call.vtt", path=FIXTURE)
    loc = pf.segments[1].locator
    text = excerpt(pf, loc)
    assert "manually" in text
