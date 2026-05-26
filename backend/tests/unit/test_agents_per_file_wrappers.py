"""Per-file wrapper modules forward shared LangGraph loop context."""

from types import SimpleNamespace

import pytest

from app.agents.per_file import docx, json, markdown, mbox, pdf, table, transcript
from app.schemas import ParsedFile


@pytest.mark.parametrize(
    ("module", "suffix_marker"),
    [
        (pdf, "PDF:"),
        (docx, "DOCX:"),
        (markdown, "Markdown/text:"),
        (table, "Table:"),
        (transcript, "Transcript:"),
        (mbox, "MBOX:"),
        (json, "JSON:"),
    ],
)
def test_per_file_wrappers_forward_run_context(monkeypatch, module, suffix_marker):
    """Every file-type wrapper forwards tracing context into the shared loop."""
    captured = {}

    def fake_loop(**kwargs):
        captured.update(kwargs)
        return "summary"

    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(per_file_iteration_cap=9))
    monkeypatch.setattr(module, "run_react_loop", fake_loop)
    parsed = ParsedFile(file_id="f1", file_name="file.test", type="md", segments=[])
    callback = object()
    provider = object()

    result = module.run(
        provider=provider,
        parsed=parsed,
        on_tool_call=callback,
        run_id="r1",
        trace_name="per_file:f1",
    )

    assert result == "summary"
    assert captured["provider"] is provider
    assert captured["parsed"] is parsed
    assert captured["on_tool_call"] is callback
    assert captured["iteration_cap"] == 9
    assert captured["run_id"] == "r1"
    assert captured["trace_name"] == "per_file:f1"
    assert suffix_marker in captured["prompt_suffix"]
