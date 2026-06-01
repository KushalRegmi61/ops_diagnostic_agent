"""Pure deterministic helpers for the per-file ProgressState working memory.

No LLM here. Everything is arithmetic over actual tool calls and results, so it
is fully unit-testable offline and impossible to hallucinate. Consumed by the
LangGraph loop's update/render nodes in ``_react_loop``.
"""
import json
import os

_FINALIZE_GUARD = int(os.getenv("AGENT_FINALIZE_GUARD", "2"))
_STALL_THRESHOLD = int(os.getenv("AGENT_STALL_THRESHOLD", "2"))

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


def _clip(value: str, n: int = 55) -> str:
    """Compact single-line preview."""
    t = " ".join(str(value).split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "..."


def render_state(ws: WorkingState, *, file_type: str) -> str:
    """Render the compact, labeled, plain-text working-memory block injected every
    turn. Plain text (not JSON) and bounded in size regardless of run length.
    """
    gaps = coverage_gaps(ws.segments_visited, ws.total_segments)[:3]
    plan_lines = "\n".join(
        f"  {'[x]' if i < ws.iteration else '[ ]'} {item}" for i, item in enumerate(ws.plan)
    ) or "  (no plan)"
    recent_wf = ", ".join(_clip(getattr(w, "name", str(w)), 40) for w in ws.workflows[-3:])
    recent_ps = ", ".join(_clip(getattr(p, "text", str(p)), 40) for p in ws.pain_signals[-3:])

    directives: list[str] = []
    if ws.steps_remaining <= _FINALIZE_GUARD:
        directives.append("Budget tight — finalize now with current findings.")
    if ws.stall_count >= _STALL_THRESHOLD:
        directives.append("Stalling — you repeated an action. Change query/region or finalize.")
    directives.append("State what evidence you still need, then call exactly one tool.")

    return (
        "=== TASK ===\n"
        f"File: {ws.file_name} ({file_type}, {ws.total_segments} segments)\n"
        "Goal: extract cited workflows, pain signals, lead rows. "
        "Call finalize_summary when the strongest evidence is captured.\n\n"
        "=== PLAN ===\n"
        f"{plan_lines}\n\n"
        f"=== PROGRESS (step {ws.iteration}/{ws.iteration_cap}, {ws.steps_remaining} left) ===\n"
        f"Coverage: {len(set(ws.segments_visited))}/{ws.total_segments} | frontier seg {ws.coverage_frontier}\n"
        f"Unvisited ranges: {gaps}\n"
        f"Queries run: {ws.queries_run[-5:]}\n"
        f"Findings: workflows={len(ws.workflows)} (recent: {recent_wf}) | "
        f"pain={len(ws.pain_signals)} (recent: {recent_ps}) | leads={len(ws.lead_rows)}\n\n"
        "=== DIRECTIVE ===\n" + "\n".join(directives)
    )
