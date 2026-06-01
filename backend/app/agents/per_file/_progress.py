"""Pure deterministic helpers for the per-file ProgressState working memory.

No LLM here. Everything is arithmetic over actual tool calls and results, so it
is fully unit-testable offline and impossible to hallucinate. Consumed by the
LangGraph loop's update/render nodes in ``_react_loop``.
"""
import json

from app.agents.per_file._state import WorkingState


def total_findings(ws: WorkingState) -> int:
    """Count all findings across the three ledgers."""
    return len(ws.workflows) + len(ws.pain_signals) + len(ws.lead_rows)


def coverage_gaps(visited: list[int], total: int) -> list[tuple[int, int]]:
    """Return sorted (start, end) inclusive ranges of segment indices NOT visited."""
    if total <= 0:
        return []
    seen = set(v for v in visited if 0 <= v < total)
    gaps: list[tuple[int, int]] = []
    start: int | None = None
    for i in range(total):
        if i not in seen:
            if start is None:
                start = i
        else:
            if start is not None:
                gaps.append((start, i - 1))
                start = None
    if start is not None:
        gaps.append((start, total - 1))
    return gaps


def signature(tool_name: str, args: dict) -> str:
    """Stable hash key for a tool call, used to detect repeated actions (stall)."""
    try:
        payload = json.dumps(args, ensure_ascii=True, sort_keys=True)
    except TypeError:
        payload = str(args)
    return f"{tool_name}:{payload}"


def saturated(ws: WorkingState, *, window: int) -> bool:
    """True when the plan is exhausted, >=1 finding exists, and finding-growth has
    stalled for ``window`` turns. Deterministic saturation signal for force-finalize.
    """
    if total_findings(ws) < 1:
        return False
    if not ws.plan or ws.iteration < len(ws.plan):   # "plan exhausted" proxy
        return False
    if len(ws.findings_at_turn) <= window:
        return False
    return ws.findings_at_turn[-1] == ws.findings_at_turn[-1 - window]
