"""Prompt context helpers and loop behavior for per-file ReAct extraction."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from app.agents.per_file._react_loop import (
    DEFAULT_MAX_STEPS,
    _segment_index_recap,
    _state_recap,
    run_react_loop,
)
from app.agents.per_file._state import WorkingState
from app.llm.base import LLMParseError
from app.schemas import LeadRow, ParsedFile, ParsedSegment, PainSignal, Source, WorkflowRecord


def _parsed() -> ParsedFile:
    """Return a small markdown ParsedFile for loop tests."""
    return ParsedFile(
        file_id="f1",
        file_name="notes.md",
        type="md",
        segments=[
            ParsedSegment(
                text="Leads wait more than 24 hours before first response.",
                locator={"type": "text", "line_start": 1, "line_end": 1},
            ),
            ParsedSegment(
                text="CSR manually copies CRM notes into email.",
                locator={"type": "text", "line_start": 2, "line_end": 2},
            ),
        ],
    )


def _source() -> Source:
    """Return a Source pointing to the first test segment."""
    return Source(
        file_id="f1",
        file_name="notes.md",
        type="md",
        locator={"type": "text", "line_start": 1, "line_end": 1},
    )


def test_segment_index_recap_includes_locator_preview():
    """Segment recap exposes both segment index and locator JSON."""
    recap = _segment_index_recap(_parsed())

    assert "[0] locator=" in recap
    assert '"line_start": 1' in recap
    assert "Leads wait more than 24 hours" in recap


def test_state_recap_includes_recent_finding_snippets():
    """Working-state recap includes compact finding names to reduce duplicates."""
    ws = WorkingState(file_id="f1", file_name="notes.md")
    ws.iteration = 3
    ws.workflows.append(
        WorkflowRecord(
            name="Inbound lead follow-up",
            actors=["Producer"],
            systems=["CRM"],
            steps=["Lead arrives", "Producer follows up"],
            manual_touchpoints=["Manual CRM note copy"],
            sources=[_source()],
        )
    )
    ws.pain_signals.append(
        PainSignal(text="Leads wait more than 24 hours before response.", category="delay", sources=[_source()])
    )
    ws.lead_rows.append(
        LeadRow(raw={"name": "Acme Corp"}, normalized={"company": "Acme Corp"}, source=_source())
    )

    recap = _state_recap(ws)

    assert "iter=3" in recap
    assert "recent_workflows=[Inbound lead follow-up]" in recap
    assert "recent_pain_signals=[Leads wait more than 24 hours before response.]" in recap
    assert "recent_lead_rows=[" in recap
    assert "Acme Corp" in recap


def test_default_max_steps_is_agent_only_default():
    """AGENT_MAX_STEPS has its own default and does not replace iteration_cap."""
    assert DEFAULT_MAX_STEPS == 12


class _ToolCallingFake(FakeMessagesListChatModel):
    """Fake chat model with the bind_tools hook required by LangChain agents."""

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


class _FakeProvider:
    """LLMProvider test double that returns a LangChain tool-calling chat model."""

    name = "fake"
    model = "fake-model"

    def __init__(self, responses=None):
        self.responses = responses or [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "cite_locator",
                        "args": {"locator": {"type": "text", "line_start": 1, "line_end": 1}},
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "finalize_summary",
                        "args": {"one_paragraph_summary": "Lead response delays are present."},
                        "id": "call_2",
                    }
                ],
            ),
        ]

    def chat_model(
        self,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        seed: int | None = None,
    ):
        return _ToolCallingFake(responses=self.responses)


class _BindingFailureProvider(_FakeProvider):
    """Provider double whose model cannot bind tools."""

    def chat_model(self, **_):
        class NoBind:
            def bind_tools(self, tools):
                raise RuntimeError("no tool calling")

        return NoBind()


def test_run_react_loop_uses_langchain_agent_tools():
    """A LangChain agent can cite evidence and finalize the summary through tools."""
    provider = _FakeProvider()
    tool_calls: list[tuple[str, dict, object]] = []

    summary = run_react_loop(
        provider=provider,
        parsed=_parsed(),
        prompt_suffix="Markdown notes.",
        iteration_cap=2,
        on_tool_call=lambda name, args, result: tool_calls.append((name, args, result)),
    )

    assert summary.one_paragraph_summary == "Lead response delays are present."
    assert [call[0] for call in tool_calls] == ["cite_locator", "finalize_summary"]
    assert tool_calls[0][2]["source"]["file_id"] == "f1"


def test_run_react_loop_immediate_finalize_succeeds():
    """The LangGraph loop can terminate on the first model tool call."""
    provider = _FakeProvider(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "finalize_summary",
                        "args": {"one_paragraph_summary": "Done immediately."},
                        "id": "call_1",
                    }
                ],
            )
        ]
    )

    summary = run_react_loop(provider=provider, parsed=_parsed())

    assert summary.one_paragraph_summary == "Done immediately."


def test_run_react_loop_plain_text_falls_back():
    """A model response without tool calls cannot be treated as a valid summary."""
    provider = _FakeProvider(responses=[AIMessage(content="I am done.")])

    summary = run_react_loop(provider=provider, parsed=_parsed())

    assert summary.one_paragraph_summary.startswith("(partial")
    assert "finalize_summary was not called" in summary.agent_notes


def test_run_react_loop_malformed_finalize_raises_llm_parse_error():
    """Malformed finalize_summary tool output raises LLMParseError — no silent drop."""
    provider = _FakeProvider(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "finalize_summary", "args": {}, "id": "call_1"}],
            )
        ]
    )

    with pytest.raises(LLMParseError) as excinfo:
        run_react_loop(provider=provider, parsed=_parsed())
    assert excinfo.value.stage == "per_file_react"
    assert "finalize_summary validation failed" in excinfo.value.message


def test_run_react_loop_tool_error_can_recover():
    """A failed non-final tool call can be observed before a later finalize call."""
    provider = _FakeProvider(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "read_segment", "args": {"segment_index": 99}, "id": "call_1"}],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "finalize_summary",
                        "args": {"one_paragraph_summary": "Recovered after tool error."},
                        "id": "call_2",
                    }
                ],
            ),
        ]
    )

    summary = run_react_loop(provider=provider, parsed=_parsed())

    assert summary.one_paragraph_summary == "Recovered after tool error."


def test_run_react_loop_binding_failure_falls_back():
    """Provider tool-binding failures return partial summaries instead of crashing."""
    summary = run_react_loop(provider=_BindingFailureProvider(), parsed=_parsed())

    assert summary.one_paragraph_summary.startswith("(partial")
    assert "tool binding failed" in summary.agent_notes


def test_run_react_loop_empty_segments_do_not_crash():
    """Empty parsed files still produce the normal fallback shape."""
    parsed = ParsedFile(file_id="f_empty", file_name="empty.md", type="md", segments=[])
    provider = _FakeProvider(responses=[AIMessage(content="No content.")])

    summary = run_react_loop(provider=provider, parsed=parsed)

    assert summary.file_id == "f_empty"
    assert summary.one_paragraph_summary.startswith("(partial")


def test_run_react_loop_tool_callback_errors_are_ignored(caplog):
    """Observer callback failures are logged but do not fail extraction."""
    def raise_callback(*_):
        raise RuntimeError("observer down")

    summary = run_react_loop(provider=_FakeProvider(), parsed=_parsed(), on_tool_call=raise_callback)

    assert summary.one_paragraph_summary == "Lead response delays are present."


def test_run_react_loop_passes_file_metadata_to_langchain_config(monkeypatch):
    """Langfuse config receives run and per-file metadata."""
    captured: dict = {}

    def fake_config(**kwargs):
        captured.update(kwargs)
        return {"callbacks": [], "tags": [], "metadata": {}}

    monkeypatch.setattr("app.agents.per_file._react_loop.langchain_config", fake_config)

    run_react_loop(provider=_FakeProvider(), parsed=_parsed(), run_id="r1", trace_name="per_file:f1")

    assert captured["session_id"] == "r1"
    assert captured["trace_name"] == "per_file:f1"
    assert captured["extra_metadata"]["file_id"] == "f1"
    assert captured["extra_metadata"]["agent_kind"] == "per_file_langgraph"


def test_run_react_loop_recursion_cap_falls_back(monkeypatch):
    """AGENT_MAX_STEPS bounds only the LangGraph agent recursion."""
    monkeypatch.setattr("app.agents.per_file._react_loop.DEFAULT_MAX_STEPS", 2)
    provider = _FakeProvider(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "read_segment", "args": {"segment_index": 0}, "id": "call_1"}],
            ),
            AIMessage(
                content="",
                tool_calls=[{"name": "read_segment", "args": {"segment_index": 1}, "id": "call_2"}],
            ),
        ]
    )

    summary = run_react_loop(provider=provider, parsed=_parsed())

    assert summary.one_paragraph_summary.startswith("(partial")
    assert "agent_max_steps=2 hit without finalize_summary" in summary.agent_notes
