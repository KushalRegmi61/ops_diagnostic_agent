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
from app.schemas import PainSignal, Source


def extract_pain_signal(ws: WorkingState, *, text: str, category: str, sources: list[Source]) -> dict:
    """Append one cited diagnostic signal to ``ws.pain_signals``.

    ``text`` should state the concrete problem, not just repeat the source
    sentence. ``category`` must be one of the known pain categories. ``sources``
    should point to the segment(s) that justify the signal.

    Returns a small acknowledgement containing the inserted signal index.
    """
    ps = PainSignal(text=text, category=category, sources=sources)
    ws.pain_signals.append(ps)
    return {"ok": True, "pain_signal_index": len(ws.pain_signals) - 1}
