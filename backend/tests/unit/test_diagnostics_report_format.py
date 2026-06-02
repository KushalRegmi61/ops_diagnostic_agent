"""Diagnostics driver (interface-stub) and report formatting."""

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from evals.diagnostics import DiagnosticsReport, FileDiagnostic, run_diagnostics
from evals.funnel import RunFunnel
from evals.loader import CorpusCase
from evals.structural import StructuralProbe


class _ToolCallingFake(FakeMessagesListChatModel):
    """Fake chat model exposing the bind_tools hook LangChain agents require."""

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


class _FakeProvider:
    """LLMProvider double that immediately finalizes, so the driver completes offline."""

    name = "fake"
    model = "fake-model"

    def chat_model(self, **_):
        return _ToolCallingFake(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "finalize_summary",
                        "args": {"one_paragraph_summary": "Stub finalize."},
                        "id": "call_1",
                    }],
                )
            ]
        )


def test_run_diagnostics_assembles_one_file_diagnostic():
    """The driver produces a complete FileDiagnostic for each case via the on_tool_call seam."""
    case = CorpusCase(file="standup_notes.md", type="md", min_pain_signals=1, min_citations=1)
    report = run_diagnostics(_FakeProvider(), cases=[case])

    assert isinstance(report, DiagnosticsReport)
    assert len(report.diagnostics) == 1
    d = report.diagnostics[0]
    assert d.file == "standup_notes.md"
    assert d.type == "md"
    assert d.funnel.terminal_reason == "model_finalize"
    assert d.failure_stage == "converges"
    assert d.probe.segment_count >= 1
