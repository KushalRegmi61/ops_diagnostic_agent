"""Offline structural probe over parsed files (segment shape + BM25 liveness)."""

from app.schemas import ParsedFile, ParsedSegment
from evals.structural import probe_structure


def _parsed(segments: list[str]) -> ParsedFile:
    """Build a ParsedFile from raw segment strings with text locators."""
    return ParsedFile(
        file_id="f1",
        file_name="x.md",
        type="md",
        segments=[
            ParsedSegment(text=t, locator={"type": "text", "line_start": i + 1, "line_end": i + 1})
            for i, t in enumerate(segments)
        ],
    )


def test_probe_healthy_multi_segment_file():
    """A healthy multi-segment file reports no flags and live BM25."""
    parsed = _parsed([
        "The intake workflow has several process steps for each new client.",
        "Manual handoff causes delay and error when the owner is missing.",
        "Contact name, email, and status are tracked per lead owner.",
    ])
    probe = probe_structure(parsed)
    assert probe.segment_count == 3
    assert probe.bm25_nonempty_rate > 0.0
    assert probe.flags == []


def test_probe_flags_single_segment():
    """A one-segment file is flagged single_segment."""
    probe = probe_structure(_parsed(["Everything is crammed into one giant block of process text."]))
    assert probe.segment_count == 1
    assert "single_segment" in probe.flags


def test_probe_flags_empty_file():
    """An empty file is flagged no_segments and never crashes."""
    probe = probe_structure(_parsed([]))
    assert probe.segment_count == 0
    assert "no_segments" in probe.flags


def test_probe_flags_tiny_segments():
    """Segments below the tiny-char threshold are flagged tiny_segments."""
    probe = probe_structure(_parsed(["a", "b", "c"]))
    assert "tiny_segments" in probe.flags
