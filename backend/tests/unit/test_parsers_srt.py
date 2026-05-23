from pathlib import Path

from app.parsers.srt import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "call.srt"


def test_parse_srt_emits_cues_with_timestamps():
    pf = parse(file_id="f1", file_name="call.srt", path=FIXTURE)
    assert pf.type == "transcript_srt"
    assert len(pf.segments) == 2
    loc = pf.segments[0].locator
    assert loc["type"] == "transcript"
    assert "0:00:01" in loc["ts_start"]


def test_excerpt_returns_cue_text():
    pf = parse(file_id="f1", file_name="call.srt", path=FIXTURE)
    text = excerpt(pf, pf.segments[1].locator)
    assert "manually" in text
