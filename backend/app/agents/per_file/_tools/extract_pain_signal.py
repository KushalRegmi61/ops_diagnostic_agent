"""Tool for recording an operational problem found in the file.

The per-file ReAct agent calls ``extract_pain_signal`` when a segment provides
evidence of wasted time, preventable errors, missing information, unclear
ownership, revenue leakage, or other friction. This is where the agent turns
observed evidence into a specific diagnostic signal.

PainSignal categories:
- ``delay``: work waits too long, follow-up is stale, SLA is missed.
- ``error``: incorrect data, rework, quality issue, or failed handoff.
- ``repetition``: duplicate entry, copy/paste, repeated manual checking.
- ``handoff``: too many people/systems or unclear ownership between steps.
- ``missing_data``: required fields, owners, dates, or context are absent.
- ``visibility_gap``: status/progress is hard to see or report.
- ``revenue_leak``: missed, stale, or mishandled opportunities cost money.

Each signal should be narrow and cited. A single file may produce multiple pain
signals if it shows distinct problems.
"""
from app.agents.per_file._state import WorkingState
from app.agents.per_file._tools._citation import _validate_sources
from app.schemas import PainSignal, ParsedFile, Source

_NO_VALID_SOURCE_HINT = (
    "every source failed to round-trip — re-check the locator against the segment index"
)


def extract_pain_signal(
    ws: WorkingState, *, parsed: ParsedFile, text: str, category: str, sources: list,
) -> dict:
    """Append one cited pain signal after validating its sources.

    Invalid sources are dropped; the signal is saved with only the kept sources
    when at least one survives, otherwise nothing is saved and ``ok`` is False
    with a corrective hint.
    """
    kept, dropped = _validate_sources(parsed, sources)
    if not kept:
        return {"ok": False, "dropped_sources": dropped, "hint": _NO_VALID_SOURCE_HINT}
    ps = PainSignal(
        text=text, category=category,
        sources=[Source(**s) if isinstance(s, dict) else s for s in kept],
    )
    ws.pain_signals.append(ps)
    return {"ok": True, "pain_signal_index": len(ws.pain_signals) - 1, "dropped_sources": dropped}
