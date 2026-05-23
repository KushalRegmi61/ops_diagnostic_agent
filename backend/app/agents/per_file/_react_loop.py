"""ReAct loop shared by every per-file agent.

Drives the think -> act -> observe cycle: each iteration the provider is asked
for a single ``{tool, args}`` JSON object, the dispatcher in ``_router.py``
runs the tool, and the result is folded into the WorkingState. The loop ends
either when the model calls ``finalize_summary`` (returning a FileSummary) or
when ``iteration_cap`` is reached (a partial FileSummary with a caveat).
"""
import json
from typing import Any

from pydantic import BaseModel

from app.agents.per_file._router import ToolCall, dispatch
from app.agents.per_file._state import WorkingState
from app.llm.base import LLMProvider
from app.prompts.per_file_brief import render_brief
from app.schemas import FileSummary, ParsedFile


class _ToolReply(BaseModel):
    """Schema the LLM must produce each iteration."""
    tool: str
    args: dict


def _state_recap(ws: WorkingState) -> str:
    """Render a one-line snapshot of the WorkingState counters for the next prompt."""
    parts = [
        f"iter={ws.iteration}",
        f"workflows={len(ws.workflows)}",
        f"pain_signals={len(ws.pain_signals)}",
        f"lead_rows={len(ws.lead_rows)}",
        f"open_questions={len(ws.open_questions)}",
    ]
    return " | ".join(parts)


def _segment_index_recap(parsed: ParsedFile, max_segments: int = 12) -> str:
    """Show the model the segment table so it can pick indices for read_segment."""
    lines: list[str] = []
    for i, seg in enumerate(parsed.segments[:max_segments]):
        preview = seg.text[:80].replace("\n", " ")
        lines.append(f"[{i}] {preview}")
    if len(parsed.segments) > max_segments:
        lines.append(f"... +{len(parsed.segments) - max_segments} more segments")
    return "\n".join(lines)


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
    ws = WorkingState(file_id=parsed.file_id, file_name=parsed.file_name)
    history: list[str] = []

    brief = render_brief(iteration_cap=iteration_cap)

    for it in range(iteration_cap):
        ws.iteration = it
        prompt = (
            brief
            + "\n\n"
            + prompt_suffix
            + "\n\nSegment index (first lines shown for picking read_segment indices):\n"
            + _segment_index_recap(parsed)
            + f"\n\nCurrent working state: {_state_recap(ws)}"
            + ("\n\nRecent tool history:\n" + "\n".join(history[-4:]) if history else "")
            + '\n\nReply with ONLY one JSON object: {"tool": "<name>", "args": {...}}'
        )

        result_dict, meta = provider.generate_json(
            prompt_name=f"per_file_{parsed.type}",
            prompt=prompt,
            schema=_ToolReply,
        )

        if not result_dict:
            ws.notes += " | LLM JSON parse failure — early finalize"
            break

        try:
            call = ToolCall(tool=result_dict["tool"], args=result_dict.get("args", {}))
        except Exception as e:
            history.append(f"BAD_REPLY {result_dict} -> {e}")
            continue

        try:
            result = dispatch(call, parsed=parsed, ws=ws)
        except Exception as e:
            history.append(f"{call.tool}({call.args}) -> ERROR {e}")
            if on_tool_call:
                on_tool_call(call.tool, call.args, {"error": str(e)})
            continue

        if on_tool_call:
            on_tool_call(call.tool, call.args, result)

        if call.tool == "finalize_summary":
            return result  # FileSummary

        history.append(f"{call.tool}({json.dumps(call.args)[:120]}) -> {str(result)[:120]}")

    # Iteration cap hit without finalize.
    ws.notes += f" | iteration_cap={iteration_cap} hit without finalize_summary"
    return FileSummary(
        file_id=ws.file_id,
        file_name=ws.file_name,
        one_paragraph_summary="(partial — iteration cap reached)",
        key_workflows=ws.workflows,
        key_pain_signals=ws.pain_signals,
        lead_rows=ws.lead_rows,
        open_questions=ws.open_questions,
        agent_notes=ws.notes,
    )
