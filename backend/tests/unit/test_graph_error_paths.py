"""Deterministic (LLM-free) tests that the graph's error paths surface errors instead of crashing.

Regression guard for the emit() stage-collision bug: when an agent raises LLMParseError,
the node must append an ExtractionError and the run must complete — not crash with TypeError.
"""
import tempfile
from pathlib import Path

import app.graph as gm
from app.graph import build_graph, initial_state
from app.parsers import parse as parsers_parse
from app.schemas import FileRef, FileSummary
from app.llm.base import LLMParseError


class _StubProvider:
    """Provider that always fails JSON generation — drives every lead node into its error path."""

    name = "stub"

    def generate_json(self, **_):
        raise LLMParseError(stage="review_summaries", message="forced lead failure")

    def chat_model(self, **_):
        raise LLMParseError(stage="review_summaries", message="no chat")


class _GoodAgent:
    """Per-file agent that returns a valid summary without calling the LLM."""

    @staticmethod
    def run(*, provider, parsed, on_tool_call, run_id, trace_name, user_context):
        return FileSummary(
            file_id=parsed.file_id, file_name=parsed.file_name,
            one_paragraph_summary="ok", key_workflows=[], key_pain_signals=[],
            lead_rows=[], open_questions=[], agent_notes="")


class _BadAgent:
    """Per-file agent that raises LLMParseError — drives per_file_one into its error path."""

    @staticmethod
    def run(*, provider, parsed, on_tool_call, run_id, trace_name, user_context):
        raise LLMParseError(stage="per_file_react", message="forced per-file failure", file_id=parsed.file_id)


def _ref(fid: str, blob: Path) -> FileRef:
    """Minimal FileRef pointing at an actual blob on disk."""
    return FileRef(file_id=fid, file_name=f"{fid}.md", blob_path=str(blob),
                   mime_type="text/markdown", parser_status="ok")


def _blob(tmp: Path, fid: str) -> Path:
    """Write a tiny markdown file and return its path."""
    p = tmp / f"{fid}.md"
    p.write_text(f"# {fid}\nmanual process\n")
    return p


def test_per_file_error_path_surfaces_extraction_error_without_crashing(tmp_path, monkeypatch):
    """A per-file agent raising LLMParseError must yield an ExtractionError, not a TypeError crash."""
    monkeypatch.setattr(gm, "get_agent_module", lambda ft: _BadAgent)
    ref = _ref("f_bad", _blob(tmp_path, "f_bad"))
    parsed = parsers_parse(file_id="f_bad", file_name="f_bad.md", path=Path(ref.blob_path), mime_type="text/markdown")
    graph = build_graph(provider=_StubProvider(), parsed_files={"f_bad": parsed}, checkpointer=None)
    final = graph.invoke(initial_state("r_bad", [ref]))   # must NOT raise
    assert any(e.file_id == "f_bad" for e in (final.get("errors") or [])), \
        "per-file LLMParseError must surface as ExtractionError"
    assert "f_bad" not in (final.get("file_summaries") or {})


def test_one_bad_file_does_not_block_siblings(tmp_path, monkeypatch):
    """Parallel fan-out: one file failing must not prevent sibling files from producing summaries."""
    class _Router:
        """Routes to _BadAgent for f_bad, _GoodAgent for all others."""

        @staticmethod
        def run(*, provider, parsed, on_tool_call, run_id, trace_name, user_context):
            if parsed.file_id == "f_bad":
                return _BadAgent.run(provider=provider, parsed=parsed, on_tool_call=on_tool_call,
                                     run_id=run_id, trace_name=trace_name, user_context=user_context)
            return _GoodAgent.run(provider=provider, parsed=parsed, on_tool_call=on_tool_call,
                                  run_id=run_id, trace_name=trace_name, user_context=user_context)

    monkeypatch.setattr(gm, "get_agent_module", lambda ft: _Router)
    refs, parsed_files = [], {}
    for fid in ("f_ok1", "f_bad", "f_ok2"):
        b = _blob(tmp_path, fid)
        refs.append(_ref(fid, b))
        parsed_files[fid] = parsers_parse(file_id=fid, file_name=f"{fid}.md", path=b, mime_type="text/markdown")
    graph = build_graph(provider=_StubProvider(), parsed_files=parsed_files, checkpointer=None)
    final = graph.invoke(initial_state("r_mix", refs))   # must NOT raise
    summaries = final.get("file_summaries") or {}
    assert "f_ok1" in summaries and "f_ok2" in summaries, "sibling files must still be summarized"
    assert "f_bad" not in summaries
    assert any(e.file_id == "f_bad" for e in (final.get("errors") or []))


def test_lead_node_error_paths_complete_without_crashing(tmp_path, monkeypatch):
    """All lead nodes hitting LLMParseError (stub provider) must complete the run, not crash on emit."""
    monkeypatch.setattr(gm, "get_agent_module", lambda ft: _GoodAgent)
    ref = _ref("f1", _blob(tmp_path, "f1"))
    parsed = parsers_parse(file_id="f1", file_name="f1.md", path=Path(ref.blob_path), mime_type="text/markdown")
    graph = build_graph(provider=_StubProvider(), parsed_files={"f1": parsed}, checkpointer=None)
    final = graph.invoke(initial_state("r_lead", [ref]))   # per_file OK, every lead node errors — must NOT raise
    assert "f1" in (final.get("file_summaries") or {})
    assert len(final.get("errors") or []) >= 1   # lead-node failures surfaced
