"""ReAct loop shared by every per-file agent.

Drives the think -> act -> observe cycle: each iteration the provider is asked
for a single ``{tool, args}`` JSON object, the dispatcher in ``_router.py``
runs the tool, and the result is folded into the WorkingState. The loop ends
either when the model calls ``finalize_summary`` (returning a FileSummary) or
when ``iteration_cap`` is reached (a partial FileSummary with a caveat).
"""
import json
import time
from typing import Any

from pydantic import BaseModel

from app.agents.per_file._router import ToolCall, dispatch
from app.agents.per_file._state import WorkingState
from app.llm.base import LLMProvider
from app.prompts.per_file_brief import render_brief
from app.schemas import FileSummary, ParsedFile
from app.structured_logging import get_logger


logger = get_logger(__name__)


class _ToolReply(BaseModel):
    """Schema the LLM must produce each iteration."""
    tool: str
    args: dict


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
        rows = ", ".join(_compact_json(lr.normalized, 70) for lr in ws.lead_rows[-3:])
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
    return "\n".join(lines)


def _validated_source_recap(sources: list[dict], max_sources: int = 5) -> str:
    """Render recently validated source candidates for the next prompt."""
    if not sources:
        return "None yet. Call cite_locator before attaching any source."
    lines: list[str] = []
    for src in sources[-max_sources:]:
        source = src["source"]
        excerpt = _clip(src.get("text", ""), 110)
        lines.append(f"- source={_compact_json(source, 180)} excerpt={excerpt}")
    return "\n".join(lines)


def _source_from_locator(parsed: ParsedFile, locator: dict) -> dict:
    """Build the Source-shaped dict the LLM can reuse after locator validation."""
    return {
        "file_id": parsed.file_id,
        "file_name": parsed.file_name,
        "type": parsed.type,
        "locator": locator,
    }


def run_react_loop(
    *,
    provider: LLMProvider,
    parsed: ParsedFile,
    prompt_suffix: str = "",
    iteration_cap: int = 6,
    on_tool_call: Any = None,  # optional callback(name, args, result) for Langfuse
) -> FileSummary:
    """Run the ReAct loop until finalize_summary is called or iteration_cap is hit.

    Returns the FileSummary built from the working state. If the cap is hit
    before finalize_summary, a fallback FileSummary is emitted with a caveat
    in agent_notes.
    """
    started = time.perf_counter()
    ws = WorkingState(file_id=parsed.file_id, file_name=parsed.file_name)
    history: list[str] = []

    brief = render_brief(
        file_id=parsed.file_id,
        file_name=parsed.file_name,
        file_type=parsed.type,
        segment_count=len(parsed.segments),
        iteration_cap=iteration_cap,
    )
    validated_sources: list[dict] = []
    logger.info(
        "agent.per_file.started",
        file_id=parsed.file_id,
        file_name=parsed.file_name,
        file_type=parsed.type,
        segment_count=len(parsed.segments),
        iteration_cap=iteration_cap,
    )

    for it in range(iteration_cap):
        ws.iteration = it
        prompt = (
            brief
            + "\n\nFile-type guidance:\n"
            + (prompt_suffix or "No additional file-type guidance.")
            + "\n\nSegment index (locator previews and first text shown for picking read_segment indices):\n"
            + _segment_index_recap(parsed)
            + f"\n\nCurrent working state: {_state_recap(ws)}"
            + "\n\nValidated source candidates:\n"
            + _validated_source_recap(validated_sources)
            + ("\n\nRecent tool history:\n" + "\n".join(history[-4:]) if history else "")
            + '\n\nReply with ONLY one JSON object: {"tool": "<name>", "args": {...}}'
        )

        iteration_started = time.perf_counter()
        logger.debug(
            "agent.per_file.iteration.started",
            file_id=parsed.file_id,
            file_type=parsed.type,
            iteration=it,
            workflow_count=len(ws.workflows),
            pain_signal_count=len(ws.pain_signals),
            lead_row_count=len(ws.lead_rows),
            open_question_count=len(ws.open_questions),
        )
        result_dict, meta = provider.generate_json(
            prompt_name=f"per_file_{parsed.type}",
            prompt=prompt,
            schema=_ToolReply,
        )

        if not result_dict:
            ws.notes += " | LLM JSON parse failure — early finalize"
            logger.warning(
                "agent.per_file.iteration.parse_failed",
                file_id=parsed.file_id,
                file_type=parsed.type,
                iteration=it,
            )
            break

        try:
            call = ToolCall(tool=result_dict["tool"], args=result_dict.get("args", {}))
        except Exception as e:
            history.append(f"BAD_REPLY {result_dict} -> {e}")
            logger.warning(
                "agent.per_file.tool_call.invalid",
                file_id=parsed.file_id,
                file_type=parsed.type,
                iteration=it,
                error=str(e),
            )
            continue

        try:
            tool_started = time.perf_counter()
            logger.debug(
                "agent.per_file.tool.started",
                file_id=parsed.file_id,
                file_type=parsed.type,
                iteration=it,
                tool=call.tool,
                arg_keys=sorted(call.args.keys()),
            )
            result = dispatch(call, parsed=parsed, ws=ws)
        except Exception as e:
            history.append(f"{call.tool}({call.args}) -> ERROR {e}")
            logger.warning(
                "agent.per_file.tool.failed",
                file_id=parsed.file_id,
                file_type=parsed.type,
                iteration=it,
                tool=call.tool,
                arg_keys=sorted(call.args.keys()),
                error=str(e),
                llm_ms=meta.latency_ms,
            )
            if on_tool_call:
                on_tool_call(call.tool, call.args, {"error": str(e)})
            continue
        logger.debug(
            "agent.per_file.tool.completed",
            file_id=parsed.file_id,
            file_type=parsed.type,
            iteration=it,
            tool=call.tool,
            result_type=type(result).__name__,
            workflow_count=len(ws.workflows),
            pain_signal_count=len(ws.pain_signals),
            lead_row_count=len(ws.lead_rows),
            open_question_count=len(ws.open_questions),
            elapsed_ms=round((time.perf_counter() - tool_started) * 1000),
        )

        if on_tool_call:
            on_tool_call(call.tool, call.args, result)

        if call.tool == "finalize_summary":
            logger.info(
                "agent.per_file.completed",
                file_id=parsed.file_id,
                file_type=parsed.type,
                iteration=it,
                finalized=True,
                workflow_count=len(result.key_workflows),
                pain_signal_count=len(result.key_pain_signals),
                lead_row_count=len(result.lead_rows),
                open_question_count=len(result.open_questions),
                elapsed_ms=round((time.perf_counter() - started) * 1000),
            )
            return result  # FileSummary

        if call.tool == "cite_locator" and isinstance(result, dict) and result.get("valid") is True:
            locator = call.args.get("locator")
            if isinstance(locator, dict):
                validated_sources.append(
                    {
                        "source": _source_from_locator(parsed, locator),
                        "text": result.get("text", ""),
                    }
                )

        history.append(f"{call.tool}({json.dumps(call.args)[:120]}) -> {str(result)[:120]}")
        logger.info(
            "agent.per_file.iteration.completed",
            file_id=parsed.file_id,
            file_type=parsed.type,
            iteration=it,
            tool=call.tool,
            llm_ms=meta.latency_ms,
            total_ms=round((time.perf_counter() - iteration_started) * 1000),
            workflows=len(ws.workflows),
            pain_signals=len(ws.pain_signals),
            lead_rows=len(ws.lead_rows),
            open_questions=len(ws.open_questions),
            parsed_json=meta.parsed_json,
            model=meta.model,
        )

    # Iteration cap hit without finalize.
    ws.notes += f" | iteration_cap={iteration_cap} hit without finalize_summary"
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
