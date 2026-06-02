"""Funnel counting, terminal-reason, and failure-stage classification for the diagnostic."""

import pytest

from evals.funnel import FunnelCollector, terminal_reason
from app.schemas import FileSummary


def test_funnel_collector_counts_each_stage():
    """FunnelCollector tallies searches, hits, reads, cites, round-trips, and extracts."""
    c = FunnelCollector()
    c("search_text", {"query": "manual follow-up"}, [{"segment_index": 0}, {"segment_index": 1}])
    c("read_segment", {"segment_index": 0}, {"text": "..."})
    c("cite_locator", {"locator": {}}, {"text": "x", "valid": True})
    c("cite_locator", {"locator": {}}, {"text": "", "valid": False})
    c("extract_pain_signal", {"text": "delay"}, {"ok": True})

    f = c.funnel
    assert f.searches_issued == 1
    assert f.search_hits_returned == 2
    assert f.reads_issued == 1
    assert f.cite_calls == 2
    assert f.cite_round_trips == 1
    assert f.extract_calls == 1
    assert f.terminal_reason == "unknown"


def _summary(*, paragraph: str, notes: str = "") -> FileSummary:
    """Build a minimal FileSummary for terminal-reason tests."""
    return FileSummary(
        file_id="f1",
        file_name="n.md",
        one_paragraph_summary=paragraph,
        key_workflows=[],
        key_pain_signals=[],
        lead_rows=[],
        open_questions=[],
        agent_notes=notes,
    )


@pytest.mark.parametrize(
    "paragraph,notes,expected",
    [
        ("(partial — iteration cap reached)", "", "fallback"),
        ("Captured 1 workflow(s) ...", "force-finalized on saturation/budget", "force_finalize"),
        ("Lead response delays are present.", "", "model_finalize"),
    ],
)
def test_terminal_reason_from_summary_shape(paragraph, notes, expected):
    """terminal_reason maps each summary fingerprint to its loop exit path."""
    assert terminal_reason(_summary(paragraph=paragraph, notes=notes)) == expected
