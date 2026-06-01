"""Unit tests for the per-file ReAct loop's steering injection.

We test ``_initial_messages`` directly — building a real ``WorkingState`` +
``ParsedFile`` lets us inspect the SystemMessage content without invoking any
LLM provider.
"""
from app.agents.per_file._react_loop import _initial_messages
from app.agents.per_file._state import WorkingState
from app.schemas import ParsedFile, ParsedSegment, RunContext


def _make_parsed() -> ParsedFile:
    return ParsedFile(
        file_id="f1",
        file_name="x.txt",
        type="txt",
        segments=[
            ParsedSegment(text="line one", locator={"type": "text", "line_start": 1, "line_end": 1}),
            ParsedSegment(text="line two", locator={"type": "text", "line_start": 2, "line_end": 2}),
        ],
    )


def test_initial_messages_without_run_context_has_no_priorities_block():
    """When the brief doesn't carry steering, the SystemMessage has no Operator priorities block."""
    parsed = _make_parsed()
    ws = WorkingState(file_id="f1", file_name="x.txt")
    messages = _initial_messages(
        brief="BRIEF_STUB",
        prompt_suffix="SUFFIX",
        parsed=parsed,
        ws=ws,
    )
    system = messages[0].content
    assert "Operator priorities" not in system


def test_initial_messages_with_steering_in_brief_propagates_through_system_message():
    """When the brief carries the steering block, the SystemMessage shows it."""
    from app.prompts.per_file_brief import render_brief
    parsed = _make_parsed()
    ws = WorkingState(file_id="f1", file_name="x.txt")
    brief = render_brief(
        file_id="f1", file_name="x.txt", file_type="txt",
        segment_count=2, iteration_cap=6,
        user_context="focus onboarding",
    )
    messages = _initial_messages(
        brief=brief,
        prompt_suffix="SUFFIX",
        parsed=parsed,
        ws=ws,
    )
    system = messages[0].content
    assert "Operator priorities" in system
    assert "focus onboarding" in system


def test_run_react_loop_accepts_run_context_kwarg(monkeypatch):
    """The public entry point accepts run_context= without raising TypeError.

    Stubs out the bound model and LangGraph machinery so no real LLM is invoked;
    the test only verifies kwarg acceptance and that the loop returns a FileSummary.
    """
    from app.agents.per_file import _react_loop as rrl

    monkeypatch.setattr(rrl, "render_brief", lambda **kw: "BRIEF_STUB")

    class _FakeBindable:
        def bind_tools(self, tools):
            return self

    class _FakeProvider:
        name = "fake"
        model = "fake"

        def chat_model(self, temperature=0.0):
            return _FakeBindable()

    class _StubGraph:
        def invoke(self, state, config=None):
            return {"messages": [], "final_summary": None, "fallback_reason": "stub"}

    monkeypatch.setattr(rrl, "_build_per_file_graph", lambda **kw: _StubGraph())

    parsed = _make_parsed()
    result = rrl.run_react_loop(
        provider=_FakeProvider(),
        parsed=parsed,
        prompt_suffix="",
        iteration_cap=2,
        run_context=RunContext(user_context="focus onboarding"),
    )
    # Stub returns a fallback path — the test confirms the kwarg is accepted
    # and a FileSummary (partial fallback shape) is returned.
    assert result is not None
    assert result.file_id == "f1"


def test_docx_wrapper_passes_user_context_through(monkeypatch):
    """The DOCX wrapper threads user_context into run_react_loop as a RunContext."""
    from app.agents.per_file import docx as docx_agent
    from app.schemas import FileSummary

    captured: dict = {}

    def fake_loop(**kwargs):
        captured.update(kwargs)
        return FileSummary(
            file_id="f1",
            file_name="x.docx",
            one_paragraph_summary="stub",
            key_workflows=[],
            key_pain_signals=[],
            lead_rows=[],
            open_questions=[],
            agent_notes="",
        )

    monkeypatch.setattr(docx_agent, "run_react_loop", fake_loop)

    from app.schemas import ParsedFile
    parsed = ParsedFile(file_id="f1", file_name="x.docx", type="docx", segments=[])
    docx_agent.run(provider=object(), parsed=parsed, user_context="focus onboarding")

    ctx = captured.get("run_context")
    assert ctx is not None, f"run_react_loop was not called with run_context; got kwargs={list(captured)}"
    assert ctx.user_context == "focus onboarding"


def test_docx_wrapper_without_user_context_passes_none_run_context(monkeypatch):
    """When the wrapper is called without user_context, run_react_loop receives run_context=None."""
    from app.agents.per_file import docx as docx_agent
    from app.schemas import FileSummary

    captured: dict = {}

    def fake_loop(**kwargs):
        captured.update(kwargs)
        return FileSummary(
            file_id="f1",
            file_name="x.docx",
            one_paragraph_summary="stub",
            key_workflows=[],
            key_pain_signals=[],
            lead_rows=[],
            open_questions=[],
            agent_notes="",
        )

    monkeypatch.setattr(docx_agent, "run_react_loop", fake_loop)

    from app.schemas import ParsedFile
    parsed = ParsedFile(file_id="f1", file_name="x.docx", type="docx", segments=[])
    docx_agent.run(provider=object(), parsed=parsed)

    assert captured.get("run_context") is None


from langchain_core.messages import AIMessage, ToolMessage
from app.agents.per_file._state import WorkingState


def _ai_tool_call(name, args, tid="t1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": tid}])


def test_apply_tool_observations_logs_query_and_segments():
    from app.agents.per_file._react_loop import _apply_tool_observations
    ws = WorkingState(file_id="f1", file_name="x", total_segments=10)
    ai = _ai_tool_call("search_text", {"query": "lead delay", "top_k": 3})
    tool = ToolMessage(content='[{"segment_index": 4}, {"segment_index": 1}]', name="search_text", tool_call_id="t1")
    _apply_tool_observations(ws, [ai, tool])
    assert "lead delay" in ws.queries_run
    assert set(ws.segments_visited) == {1, 4}
    assert ws.coverage_frontier == 4


def test_apply_tool_observations_read_segment_marks_visited():
    from app.agents.per_file._react_loop import _apply_tool_observations
    ws = WorkingState(file_id="f1", file_name="x", total_segments=10)
    ai = _ai_tool_call("read_segment", {"segment_index": 7})
    tool = ToolMessage(content='{"text": "...", "locator": {}}', name="read_segment", tool_call_id="t1")
    _apply_tool_observations(ws, [ai, tool])
    assert 7 in ws.segments_visited


def test_update_stall_increments_on_repeated_signature():
    from app.agents.per_file._react_loop import _update_stall
    ws = WorkingState(file_id="f1", file_name="x")
    ai = _ai_tool_call("search_text", {"query": "same"})
    _update_stall(ws, ai)
    assert ws.stall_count == 0          # first occurrence
    _update_stall(ws, _ai_tool_call("search_text", {"query": "same"}))
    assert ws.stall_count == 1          # repeat
    _update_stall(ws, _ai_tool_call("search_text", {"query": "different"}))
    assert ws.stall_count == 0          # reset on change


def test_force_finalize_builds_real_summary_from_findings():
    from app.agents.per_file._react_loop import _force_finalize_summary
    from app.agents.per_file._state import WorkingState
    from app.schemas import WorkflowRecord, PainSignal

    ws = WorkingState(file_id="f1", file_name="x.txt")
    ws.workflows = [
        WorkflowRecord(name="wf-a", actors=[], systems=[], steps=[], manual_touchpoints=[], sources=[])
    ]
    ws.pain_signals = [
        PainSignal(text="ps-a", category="delay", sources=[]),
        PainSignal(text="ps-b", category="error", sources=[]),
    ]
    summary = _force_finalize_summary(ws)
    assert summary.file_id == "f1"
    assert "partial" not in summary.one_paragraph_summary.lower()
    assert summary.one_paragraph_summary.strip() != ""
    assert summary.key_workflows == ws.workflows
    assert summary.key_pain_signals == ws.pain_signals


def test_route_after_update_finalizes_on_finalize_summary_call():
    from app.agents.per_file._react_loop import _route_after_update
    ws = WorkingState(file_id="f1", file_name="x", iteration_cap=6)
    ws.iteration = 1
    ai = _ai_tool_call("finalize_summary", {"one_paragraph_summary": "done"})
    assert _route_after_update({"messages": [ai]}, ws) == "finalize"


def test_route_after_update_force_finalizes_when_budget_tight():
    from app.agents.per_file._react_loop import _route_after_update
    ws = WorkingState(file_id="f1", file_name="x", iteration_cap=6)
    ws.iteration = 5                  # steps_remaining == 1 <= FINALIZE_GUARD
    ws.workflows = ["wf"]             # has a finding to keep
    ai = _ai_tool_call("search_text", {"query": "q"})
    assert _route_after_update({"messages": [ai]}, ws) == "force_finalize"


def test_route_after_update_continues_otherwise():
    from app.agents.per_file._react_loop import _route_after_update
    ws = WorkingState(file_id="f1", file_name="x", iteration_cap=6)
    ws.iteration = 1
    ai = _ai_tool_call("search_text", {"query": "q"})
    assert _route_after_update({"messages": [ai]}, ws) == "render"


def test_route_after_update_budget_tight_zero_findings_routes_to_fallback():
    from app.agents.per_file._react_loop import _route_after_update
    ws = WorkingState(file_id="f1", file_name="x", iteration_cap=6)
    ws.iteration = 5            # steps_remaining == 1 <= FINALIZE_GUARD, no findings
    ai = _ai_tool_call("search_text", {"query": "q"})
    assert _route_after_update({"messages": [ai]}, ws) == "fallback"
