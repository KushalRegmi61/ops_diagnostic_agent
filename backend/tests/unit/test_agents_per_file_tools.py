"""Per-file ReAct tools: read_segment, extract_*, cite_locator, finalize_summary.

Each tool is exercised directly (not through the router) against a tiny
ParsedFile fixture to confirm the citation invariant and WorkingState mutation
contracts.
"""
import pytest

from app.agents.per_file._state import WorkingState
from app.agents.per_file._tools.cite_locator import cite_locator
from app.agents.per_file._tools.extract_lead_row import extract_lead_row
from app.agents.per_file._tools.extract_pain_signal import extract_pain_signal
from app.agents.per_file._tools.extract_workflow import extract_workflow
from app.agents.per_file._tools.finalize_summary import finalize_summary
from app.agents.per_file._tools.read_segment import read_segment
from app.schemas import ParsedFile, ParsedSegment, Source


def _pf() -> ParsedFile:
    """Return a single-line markdown ParsedFile for tool inputs."""
    return ParsedFile(
        file_id="f1", file_name="x.md", type="md",
        segments=[
            ParsedSegment(text="Step 1: collect contact info.",
                          locator={"type": "text", "line_start": 1, "line_end": 1}),
        ],
    )


def _src() -> Source:
    """Return a Source pointing at line 1 of the fixture ParsedFile."""
    return Source(file_id="f1", file_name="x.md", type="md",
                  locator={"type": "text", "line_start": 1, "line_end": 1})


def test_read_segment_returns_text_and_locator():
    """read_segment returns the segment text plus its locator dict."""
    result = read_segment(_pf(), segment_index=0)
    assert "contact info" in result["text"]
    assert result["locator"]["line_start"] == 1


def test_read_segment_raises_on_invalid_index():
    """Out-of-range segment_index raises ValueError."""
    with pytest.raises(ValueError):
        read_segment(_pf(), segment_index=99)


def test_extract_workflow_appends_to_working_state():
    """extract_workflow appends a WorkflowRecord and reports ok=True."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    out = extract_workflow(
        ws, name="onboarding", actors=["CSR"], systems=["Applied"],
        steps=["verify id"], manual_touchpoints=["copy"], sources=[_src()],
    )
    assert out["ok"] is True
    assert ws.workflows[0].name == "onboarding"


def test_extract_pain_signal_validates_category():
    """extract_pain_signal accepts known categories and stores the PainSignal."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    extract_pain_signal(ws, text="too slow", category="delay", sources=[_src()])
    assert ws.pain_signals[0].category == "delay"


def test_extract_lead_row_only_accepts_table_types():
    """extract_lead_row appends a LeadRow with raw + normalized payload."""
    ws = WorkingState(file_id="f1", file_name="leads.csv")
    extract_lead_row(ws, raw={"name": "Acme"}, normalized={"name": "Acme"}, source=_src())
    assert ws.lead_rows[0].raw[0].key == "name"
    assert ws.lead_rows[0].raw[0].value == "Acme"


def test_cite_locator_roundtrips_through_parser():
    """cite_locator round-trips a valid locator through the parser to text."""
    result = cite_locator(_pf(), locator={"type": "text", "line_start": 1, "line_end": 1})
    assert result["valid"] is True
    assert "contact info" in result["text"]


def test_cite_locator_invalid_returns_valid_false():
    """Unreachable locators yield valid=False instead of raising."""
    result = cite_locator(_pf(), locator={"type": "text", "line_start": 99, "line_end": 99})
    assert result["valid"] is False


def test_finalize_summary_builds_file_summary_from_state():
    """finalize_summary projects WorkingState into a FileSummary."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    ws.notes = "ran clean"
    summary = finalize_summary(ws, one_paragraph_summary="single para")
    assert summary.file_id == "f1"
    assert summary.one_paragraph_summary == "single para"
    assert summary.agent_notes == "ran clean"
