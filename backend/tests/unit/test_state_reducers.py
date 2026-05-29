"""Unit tests for DiagnosticState reducers used by the parallel per-file fan-out."""
from app.state import merge_file_summaries
from app.schemas import FileSummary


def _summary(file_id: str) -> FileSummary:
    """Minimal valid FileSummary for reducer tests."""
    return FileSummary(
        file_id=file_id,
        file_name=f"{file_id}.txt",
        one_paragraph_summary="s",
        key_workflows=[],
        key_pain_signals=[],
        lead_rows=[],
        open_questions=[],
        agent_notes="",
    )


def test_merge_combines_disjoint_branch_outputs():
    """Two parallel branches each contributing one file_id merge into one dict."""
    left = {"f1": _summary("f1")}
    right = {"f2": _summary("f2")}
    merged = merge_file_summaries(left, right)
    assert set(merged) == {"f1", "f2"}


def test_merge_right_wins_on_redo():
    """A redo pass re-runs a file; the newer (right) summary replaces the old one."""
    old = {"f1": _summary("f1")}
    new = {"f1": _summary("f1")}
    merged = merge_file_summaries(old, new)
    assert merged["f1"] is new["f1"]


def test_merge_tolerates_none():
    """Reducer treats None operands as empty dicts (initial channel state)."""
    only_right = merge_file_summaries(None, {"f1": _summary("f1")})
    assert set(only_right) == {"f1"}
    only_left = merge_file_summaries({"f1": _summary("f1")}, None)
    assert set(only_left) == {"f1"}
    assert merge_file_summaries(None, None) == {}
