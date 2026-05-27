"""Shared 'Operator priorities' block renderer.

Single source of truth for the phrasing of the optional steering preamble
injected into per-file and lead-agent prompts. Each ``Role`` member maps to
a role-specific instruction so the steering signal is interpreted consistently
across the graph.

Returns ``""`` whenever ``run_context`` is missing or carries no steering —
guaranteeing prompts are byte-identical to baseline when no operator
context is supplied.
"""
from enum import Enum

from app.schemas import RunContext


class Role(str, Enum):
    """Where in the pipeline the steering block is being rendered."""

    PER_FILE = "per_file"
    SYNTHESIS = "synthesis"
    RANKING = "ranking"
    SELECTION = "selection"
    FRAMING = "framing"
    ACCEPTANCE = "acceptance"


_ROLE_TEMPLATES: dict[Role, str] = {
    Role.PER_FILE: (
        "Operator priorities (steering hint — bias your exploration order):\n"
        "{ctx}\n\n"
        "Use these priorities to choose which segments to inspect first and "
        "what to search for. Still extract any significant workflow, pain "
        "signal, or lead row you encounter, even if outside these priorities. "
        "Downstream synthesis handles prioritization."
    ),
    Role.SYNTHESIS: (
        "Operator priorities:\n"
        "{ctx}\n\n"
        "When building the IntakeBundle, give weight to workflows and pain "
        "signals aligned with these priorities. Do not drop unrelated cited "
        "material — preserve it so downstream nodes can reason over it."
    ),
    Role.RANKING: (
        "Operator priorities:\n"
        "{ctx}\n\n"
        "Use these as a ranking tiebreak: when two bottlenecks have comparable "
        "impact, rank the priority-aligned one higher. Do not omit bottlenecks "
        "that fall outside the priorities — rank them lower instead."
    ),
    Role.SELECTION: (
        "Operator priorities:\n"
        "{ctx}\n\n"
        "Prefer fastest-win opportunities that address these priorities, even "
        "if not the largest ROI. State the reasoning explicitly in the "
        "selection rationale."
    ),
    Role.FRAMING: (
        "Operator priorities:\n"
        "{ctx}\n\n"
        "Frame the Blueprint summary and steps around how they address these "
        "priorities. Cite the specific evidence that links each step back to a "
        "stated priority."
    ),
    Role.ACCEPTANCE: (
        "Operator priorities:\n"
        "{ctx}\n\n"
        "If the Blueprint does not address these priorities (either by acting "
        "on them or by explaining why they were deprioritized), set "
        "passed=false with reason citing the gap. If your review check itself "
        "errors, default passed=true — never block on review-layer flakiness."
    ),
}


def render_priorities_block(*, role: Role, run_context: RunContext | None) -> str:
    """Render the role-specific 'Operator priorities' block, or '' when no steering is set.

    A non-empty result always begins with two leading newlines so callers can
    concatenate safely: ``prompt + render_priorities_block(...) + tail``.
    """
    if run_context is None or not run_context.has_steering():
        return ""
    template = _ROLE_TEMPLATES[role]
    assert run_context.user_context is not None  # has_steering() guarantees this
    return "\n\n" + template.format(ctx=run_context.user_context.strip())
