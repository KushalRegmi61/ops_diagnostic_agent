"""LangGraph tool loop shared by every per-file agent.

Drives a compact model -> tool -> model graph over file-local StructuredTools.
The graph ends when the model calls ``finalize_summary`` or falls back to a
partial FileSummary when the agent stops, errors, or reaches its step cap.
"""
import json
import os
import re
import time
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.agents.per_file import _progress
from app.agents.per_file._plan import make_plan
from app.agents.per_file._router import build_tools
from app.agents.per_file._state import WorkingState
from app.llm.base import LLMParseError, LLMProvider
from app.observability import langchain_config
from app.prompts.per_file_brief import render_brief
from app.schemas import FileSummary, ParsedFile, RunContext
from app.structured_logging import get_logger


logger = get_logger(__name__)
DEFAULT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "12"))
COMPACT_EVERY = int(os.getenv("AGENT_COMPACT_EVERY", "4"))       # sawtooth period (turns)
FINALIZE_GUARD = int(os.getenv("AGENT_FINALIZE_GUARD", "2"))     # force-finalize when steps_remaining <= this
SATURATION_WINDOW = int(os.getenv("AGENT_SATURATION_WINDOW", "2"))  # turns of zero finding-growth before saturation
FILE_NAME_PATTERN = re.compile(r"([A-Za-z0-9][A-Za-z0-9_\- ]{0,200}\.[A-Za-z0-9]{1,8})")


class _PerFileGraphState(TypedDict, total=False):
    """Internal LangGraph state for a single per-file extraction."""

    messages: Annotated[list[BaseMessage], add_messages]
    final_summary: FileSummary | None
    fallback_reason: str | None


def _clip(value: str, max_chars: int = 90) -> str:
    """Return a compact single-line preview for prompt recaps."""
    text = " ".join(value.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def _compact_json(value: Any, max_chars: int = 160) -> str:
    """Serialize prompt context compactly, with a stable fallback."""
    try:
        text = json.dumps(value, ensure_ascii=True, sort_keys=True)
    except TypeError:
        text = str(value)
    return _clip(text, max_chars=max_chars)


def _state_recap(ws: WorkingState) -> str:
    """Render a compact WorkingState snapshot for the next prompt."""
    parts = [
        f"iter={ws.iteration}",
        f"workflows={len(ws.workflows)}",
        f"pain_signals={len(ws.pain_signals)}",
        f"lead_rows={len(ws.lead_rows)}",
        f"open_questions={len(ws.open_questions)}",
    ]
    if ws.workflows:
        names = ", ".join(_clip(wf.name, 40) for wf in ws.workflows[-3:])
        parts.append(f"recent_workflows=[{names}]")
    if ws.pain_signals:
        signals = ", ".join(_clip(ps.text, 55) for ps in ws.pain_signals[-3:])
        parts.append(f"recent_pain_signals=[{signals}]")
    if ws.lead_rows:
        rows = ", ".join(
            _compact_json({kv.key: kv.value for kv in lr.normalized}, 70)
            for lr in ws.lead_rows[-3:]
        )
        parts.append(f"recent_lead_rows=[{rows}]")
    return " | ".join(parts)


def _segment_index_recap(parsed: ParsedFile, max_segments: int = 12) -> str:
    """Show the model the segment table so it can pick indices for read_segment."""
    lines: list[str] = []
    for i, seg in enumerate(parsed.segments[:max_segments]):
        preview = _clip(seg.text, 80)
        locator = _compact_json(seg.locator, 130)
        lines.append(f"[{i}] locator={locator} text={preview}")
    if len(parsed.segments) > max_segments:
        lines.append(f"... +{len(parsed.segments) - max_segments} more segments")
    return "\n".join(lines) if lines else "No parsed segments available."


def run_react_loop(
    *,
    provider: LLMProvider,
    parsed: ParsedFile,
    prompt_suffix: str = "",
    iteration_cap: int = 6,
    on_tool_call: Any = None,  # optional callback(name, args, result) for Langfuse
    run_id: str | None = None,
    trace_name: str | None = None,
    run_context: RunContext | None = None,
) -> FileSummary:
    """Run an explicit LangGraph tool-calling loop until finalize_summary or fallback.

    ``run_context`` is injected into the per-file brief as a steering hint. It
    biases exploration order without filtering what makes it into the
    FileSummary — recall is preserved at the per-file layer.
    """
    started = time.perf_counter()
    ws = WorkingState(
        file_id=parsed.file_id,
        file_name=parsed.file_name,
        total_segments=len(parsed.segments),
        iteration_cap=iteration_cap,
    )
    ws.plan = make_plan(provider, parsed)

    brief = render_brief(
        file_id=parsed.file_id,
        file_name=parsed.file_name,
        file_type=parsed.type,
        segment_count=len(parsed.segments),
        iteration_cap=iteration_cap,
        user_context=run_context.user_context if (run_context and run_context.has_steering()) else None,
    )
    logger.info(
        "agent.per_file.started",
        file_id=parsed.file_id,
        file_name=parsed.file_name,
        file_type=parsed.type,
        segment_count=len(parsed.segments),
        iteration_cap=iteration_cap,
        agent_max_steps=DEFAULT_MAX_STEPS,
        run_id=run_id,
        trace_name=trace_name,
        user_context_chars=len(run_context.user_context) if (run_context and run_context.user_context) else 0,
        has_steering=run_context.has_steering() if run_context else False,
    )

    tools = list(build_tools(parsed, ws, agent_mode=True).values())
    try:
        chat_model = provider.chat_model(temperature=0.0)  # type: ignore[attr-defined]
        bound_model = chat_model.bind_tools(tools)
    except Exception as e:
        reason = f"tool binding failed: {e}"
        logger.warning(
            "agent.per_file.failed",
            file_id=parsed.file_id,
            file_type=parsed.type,
            error=reason,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
        return _partial_summary(ws, parsed, started, reason=reason)

    graph = _build_per_file_graph(bound_model=bound_model, tools=tools, ws=ws, parsed=parsed)
    messages = _initial_messages(
        brief=brief,
        prompt_suffix=prompt_suffix,
        parsed=parsed,
        ws=ws,
    )
    config = langchain_config(
        provider=getattr(provider, "name", type(provider).__name__),
        model=getattr(provider, "model", type(provider).__name__),
        prompt_name=f"per_file_{parsed.type}",
        session_id=run_id,
        trace_name=trace_name,
        extra_tags=["per_file", parsed.type],
        extra_metadata={
            "agent_kind": "per_file_langgraph",
            "file_id": parsed.file_id,
            "file_name": parsed.file_name,
            "file_type": parsed.type,
            "segment_count": len(parsed.segments),
            "iteration_cap": iteration_cap,
            "agent_max_steps": DEFAULT_MAX_STEPS,
            "user_context_chars": len(run_context.user_context) if (run_context and run_context.user_context) else 0,
            "has_steering": run_context.has_steering() if run_context else False,
        },
    )
    # recursion_limit is now a pure backstop: each turn is ~4 super-steps, so allow
    # iteration_cap turns with headroom. Budget is enforced by ws.iteration / force-finalize.
    config["recursion_limit"] = iteration_cap * 4 + 8

    try:
        result = graph.invoke(
            {"messages": messages, "final_summary": None, "fallback_reason": None},
            config=config,
        )
    except GraphRecursionError:
        reason = f"iteration_cap={iteration_cap} exhausted without finalize_summary (recursion backstop)"
        logger.warning(
            "agent.per_file.recursion_limit",
            file_id=parsed.file_id,
            file_type=parsed.type,
            agent_max_steps=DEFAULT_MAX_STEPS,
            iteration_cap=iteration_cap,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
        return _partial_summary(ws, parsed, started, reason=reason)
    except LLMParseError:
        # Re-raise so the graph node wrapper can append a structured ExtractionError.
        raise
    except Exception as e:
        reason = f"LangGraph agent failed: {e}"
        logger.warning(
            "agent.per_file.failed",
            file_id=parsed.file_id,
            file_type=parsed.type,
            error=str(e),
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
        return _partial_summary(ws, parsed, started, reason=reason)

    messages = result.get("messages", []) if isinstance(result, dict) else []
    _emit_tool_callbacks(messages, on_tool_call)
    summary = result.get("final_summary") if isinstance(result, dict) else None
    if summary is not None:
        logger.info(
            "agent.per_file.completed",
            file_id=parsed.file_id,
            file_type=parsed.type,
            finalized=True,
            workflow_count=len(summary.key_workflows),
            pain_signal_count=len(summary.key_pain_signals),
            lead_row_count=len(summary.lead_rows),
            open_question_count=len(summary.open_questions),
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
        return summary

    reason = result.get("fallback_reason") if isinstance(result, dict) else None
    return _partial_summary(
        ws,
        parsed,
        started,
        reason=reason or f"iteration_cap={iteration_cap} exhausted without finalize_summary",
    )


def _initial_messages(
    *,
    brief: str,
    prompt_suffix: str,
    parsed: ParsedFile,
    ws: WorkingState,
) -> list[BaseMessage]:
    """Build the initial system/user messages for the per-file LangGraph."""
    system = (
        brief
        + "\n\nFile-type guidance:\n"
        + (prompt_suffix or "No additional file-type guidance.")
        + "\n\nUse tools to inspect evidence and build findings. "
        + "Call cite_locator before using a locator as a source. "
        + "Call finalize_summary when the file summary is complete."
    )
    user = (
        "Segment index (locator previews and first text shown for picking read_segment indices):\n"
        + _segment_index_recap(parsed)
    )
    return [SystemMessage(content=system), HumanMessage(content=user)]


def _apply_tool_observations(ws: WorkingState, messages: list[Any]) -> None:
    """Deterministically fold the latest tool call + its result into ProgressState.

    Logs queries, records visited segment indices, and advances the coverage
    frontier. No LLM; pure bookkeeping over observable tool I/O.
    """
    last_ai = _last_ai_message(messages)
    if last_ai is None:
        return
    calls = _tool_calls(last_ai)
    if not calls:
        return
    call = calls[-1]
    name, args = call.get("name"), call.get("args") or {}

    if name == "search_text":
        q = str(args.get("query", "")).strip()
        if q:
            ws.queries_run.append(q)
        result = _tool_result_for(messages, call.get("id"))
        for idx in _segment_indices(result):
            if idx not in ws.segments_visited:
                ws.segments_visited.append(idx)
            ws.coverage_frontier = max(ws.coverage_frontier, idx)
    elif name == "read_segment":
        idx = args.get("segment_index")
        if isinstance(idx, int):
            if idx not in ws.segments_visited:
                ws.segments_visited.append(idx)
            ws.coverage_frontier = max(ws.coverage_frontier, idx)


def _tool_result_for(messages: list[Any], tool_call_id: str | None) -> Any:
    """Return the parsed ToolMessage content matching a tool_call id."""
    if tool_call_id is None:
        return None
    for m in reversed(messages):
        if isinstance(m, ToolMessage) and m.tool_call_id == tool_call_id:
            try:
                return json.loads(m.content)
            except Exception:
                return m.content
    return None


def _segment_indices(result: Any) -> list[int]:
    """Extract segment_index ints from a search_text result payload."""
    out: list[int] = []
    if isinstance(result, list):
        for hit in result:
            if isinstance(hit, dict) and isinstance(hit.get("segment_index"), int):
                out.append(hit["segment_index"])
    return out


def _update_stall(ws: WorkingState, last_ai: AIMessage | None) -> None:
    """Increment stall_count on a repeated (tool, args) signature; reset on change."""
    calls = _tool_calls(last_ai) if last_ai is not None else []
    if not calls:
        return
    call = calls[-1]
    sig = _progress.signature(call.get("name", ""), call.get("args") or {})
    if sig == ws.last_signature:
        ws.stall_count += 1
    else:
        ws.stall_count = 0
    ws.last_signature = sig


def _build_per_file_graph(*, bound_model: Any, tools: list[Any], ws: WorkingState, parsed: ParsedFile):
    """Build the converging loop: render -> agent -> tools -> update -> route."""

    def render_node(state: _PerFileGraphState) -> dict:
        """Inject a fresh ProgressState block as a HumanMessage before each turn."""
        block = _progress.render_state(ws, file_type=parsed.type)
        return {"messages": [HumanMessage(content=block)]}

    def agent_node(state: _PerFileGraphState, config: RunnableConfig) -> dict:
        """Increment iteration counter and invoke the bound model."""
        ws.iteration += 1
        response = bound_model.invoke(state.get("messages", []), config=config)
        return {"messages": [response]}

    def update_node(state: _PerFileGraphState) -> dict:
        """Deterministically recompute ProgressState (coverage, stall signature, per-turn findings count) and compact the transcript on the sawtooth period."""
        messages = state.get("messages", [])
        last_ai = _last_ai_message(messages)
        _apply_tool_observations(ws, messages)
        _update_stall(ws, last_ai)
        ws.findings_at_turn.append(_progress.total_findings(ws))
        removals: list[Any] = []
        if COMPACT_EVERY > 0 and ws.iteration % COMPACT_EVERY == 0:
            keep_tail = messages[-2:]
            for m in messages:
                if isinstance(m, SystemMessage) or m in keep_tail:
                    continue
                mid = getattr(m, "id", None)
                if mid is not None:
                    removals.append(RemoveMessage(id=mid))
        return {"messages": removals}

    def finalize_node(state: _PerFileGraphState) -> dict:
        """Extract and validate finalize_summary output, or raise LLMParseError."""
        summary, error = _final_summary_or_error(state.get("messages", []))
        if summary is not None:
            return {"final_summary": summary}
        raise LLMParseError(
            stage="per_file_react", file_id=ws.file_id,
            message=error or "finalize_summary output was invalid",
        )

    def force_finalize_node(state: _PerFileGraphState) -> dict:
        """Saturation/budget guard fired -- synthesize a real summary from findings."""
        return {"final_summary": _force_finalize_summary(ws)}

    def fallback_node(state: _PerFileGraphState) -> dict:
        """Populate fallback_reason when the agent stopped without finalizing."""
        if state.get("fallback_reason"):
            return {}
        last_ai = _last_ai_message(state.get("messages", []))
        if last_ai is None:
            return {"fallback_reason": "agent did not produce a model response"}
        if not _tool_calls(last_ai):
            return {"fallback_reason": "finalize_summary was not called"}
        return {"fallback_reason": "agent stopped before finalize_summary"}

    graph = StateGraph(_PerFileGraphState)
    graph.add_node("render", render_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    graph.add_node("update", update_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("force_finalize", force_finalize_node)
    graph.add_node("fallback", fallback_node)
    graph.set_entry_point("render")
    graph.add_edge("render", "agent")
    graph.add_conditional_edges("agent", _route_after_agent, {"tools": "tools", "fallback": "fallback"})
    graph.add_edge("tools", "update")
    graph.add_conditional_edges(
        "update",
        lambda state: _route_after_update(state, ws),
        {"finalize": "finalize", "force_finalize": "force_finalize",
         "render": "render", "fallback": "fallback"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("force_finalize", END)
    graph.add_edge("fallback", END)
    return graph.compile()


def _route_after_agent(state: _PerFileGraphState) -> str:
    """Route model responses with tool calls to tools; otherwise fallback."""
    last_ai = _last_ai_message(state.get("messages", []))
    if last_ai is None or not _tool_calls(last_ai):
        return "fallback"
    return "tools"


def _route_after_update(state: _PerFileGraphState, ws: WorkingState) -> str:
    """Terminal routing: explicit finalize, else (on budget/saturation) force-finalize
    when findings exist or fall back cleanly when none, else continue."""
    last_ai = _last_ai_message(state.get("messages", []))
    if last_ai is not None:
        for call in _tool_calls(last_ai):
            if call.get("name") == "finalize_summary":
                return "finalize"
    if ws.steps_remaining <= FINALIZE_GUARD:
        return "force_finalize" if _progress.total_findings(ws) >= 1 else "fallback"
    if _progress.saturated(ws, window=SATURATION_WINDOW):
        return "force_finalize"
    return "render"


def _last_ai_message(messages: list[Any]) -> AIMessage | None:
    """Return the latest AIMessage in a LangChain/LangGraph transcript."""
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message
    return None


def _tool_calls(message: AIMessage) -> list[dict]:
    """Return tool calls from an AIMessage, tolerating provider-specific shapes."""
    calls = getattr(message, "tool_calls", None) or []
    return [call for call in calls if isinstance(call, dict)]


def _final_summary_from_messages(messages: list[Any]) -> FileSummary | None:
    """Extract the finalize_summary tool output from a LangChain agent transcript."""
    summary, _ = _final_summary_or_error(messages)
    return summary


def _final_summary_or_error(messages: list[Any]) -> tuple[FileSummary | None, str | None]:
    """Extract and validate the finalize_summary tool output with an error reason."""
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and message.name == "finalize_summary":
            try:
                return FileSummary.model_validate_json(message.content), None
            except Exception as json_exc:
                try:
                    return FileSummary.model_validate(json.loads(message.content)), None
                except Exception as model_exc:
                    return (
                        None,
                        f"finalize_summary validation failed: {json_exc}; {model_exc}",
                    )
    return None, "finalize_summary tool output was not found"


def _emit_tool_callbacks(messages: list[Any], on_tool_call: Any) -> None:
    """Replay LangChain tool calls to the existing optional tool callback."""
    if on_tool_call is None:
        return
    pending: dict[str, dict] = {}
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                pending[call["id"]] = {"name": call["name"], "args": call.get("args") or {}}
        elif isinstance(message, ToolMessage):
            call = pending.get(message.tool_call_id)
            if call:
                try:
                    result = json.loads(message.content)
                except Exception:
                    result = message.content
                try:
                    on_tool_call(call["name"], call["args"], result)
                except Exception as exc:
                    logger.warning(
                        "agent.per_file.tool_callback_failed",
                        tool=call["name"],
                        error=str(exc),
                    )


def _partial_summary(
    ws: WorkingState,
    parsed: ParsedFile,
    started: float,
    *,
    reason: str | None = None,
) -> FileSummary:
    """Return the existing partial summary fallback shape."""
    if reason:
        ws.notes = (ws.notes + " | " if ws.notes else "") + reason
    summary = FileSummary(
        file_id=ws.file_id,
        file_name=ws.file_name,
        one_paragraph_summary="(partial — iteration cap reached)",
        key_workflows=ws.workflows,
        key_pain_signals=ws.pain_signals,
        lead_rows=ws.lead_rows,
        open_questions=ws.open_questions,
        agent_notes=ws.notes,
    )
    logger.warning(
        "agent.per_file.completed",
        file_id=parsed.file_id,
        file_type=parsed.type,
        finalized=False,
        workflow_count=len(summary.key_workflows),
        pain_signal_count=len(summary.key_pain_signals),
        lead_row_count=len(summary.lead_rows),
        open_question_count=len(summary.open_questions),
        elapsed_ms=round((time.perf_counter() - started) * 1000),
    )
    return summary


def _force_finalize_summary(ws: WorkingState) -> FileSummary:
    """Build a REAL FileSummary from accumulated findings without an LLM call.

    Fired by the saturation/budget guard. Produces a genuine one-paragraph summary
    (not the '(partial …)' fallback string) so a run that found anything always
    returns a real summary.
    """
    paragraph = (
        f"Captured {len(ws.workflows)} workflow(s), {len(ws.pain_signals)} pain signal(s), "
        f"and {len(ws.lead_rows)} lead row(s) from {ws.file_name} across "
        f"{len(set(ws.segments_visited))} inspected segment(s)."
    )
    return FileSummary(
        file_id=ws.file_id,
        file_name=ws.file_name,
        one_paragraph_summary=paragraph,
        key_workflows=ws.workflows,
        key_pain_signals=ws.pain_signals,
        lead_rows=ws.lead_rows,
        open_questions=ws.open_questions,
        agent_notes=(ws.notes + " | force-finalized on saturation/budget").strip(" |"),
    )
