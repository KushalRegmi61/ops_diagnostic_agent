"""Diagnostics driver (interface-stub) and report formatting."""

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from evals.diagnostics import DiagnosticsReport, FileDiagnostic, format_report, run_diagnostics
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


def test_format_report_includes_header_and_each_file_row():
    """The rendered table carries a header plus one row per file with its stage."""
    report = DiagnosticsReport(diagnostics=[
        FileDiagnostic(
            file="onboarding_sop.docx",
            type="docx",
            funnel=RunFunnel(terminal_reason="fallback", searches_issued=6, search_hits_returned=0),
            probe=StructuralProbe(
                segment_count=1, seg_chars_min=900, seg_chars_median=900,
                seg_chars_max=900, bm25_nonempty_rate=0.0, flags=["single_segment", "bm25_dead"],
            ),
            failure_stage="retrieval_or_parser",
        ),
    ])

    table = format_report(report)
    assert "file" in table and "stage" in table
    assert "onboarding_sop.docx" in table
    assert "retrieval_or_parser" in table
    assert "single_segment,bm25_dead" in table
