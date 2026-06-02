"""Funnel counting, terminal-reason, and failure-stage classification for the diagnostic."""

from evals.funnel import FunnelCollector


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
