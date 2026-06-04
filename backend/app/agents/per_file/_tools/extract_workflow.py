"""Tool for recording a business process described or implied by the file.

The per-file ReAct agent calls ``extract_workflow`` when it has enough cited
evidence to describe how work currently moves through people and systems. This
is for process-level facts, not individual lead records and not broad final
summaries.

Good workflow examples:
- inbound lead intake from web form to CRM to producer follow-up
- quote request triage from shared inbox to AMS entry
- renewal review steps across CSR, producer, and carrier portal

Each WorkflowRecord should include the actors involved, systems touched,
ordered steps when known, manual touchpoints, and source citations. Downstream
lead agents use these records to map operations and find bottlenecks.
"""
from app.agents.per_file._state import WorkingState
from app.agents.per_file._tools._citation import _validate_sources
from app.schemas import ParsedFile, Source, WorkflowRecord

_NO_VALID_SOURCE_HINT = (
    "every source failed to round-trip — re-check the locator against the segment index"
)


def extract_workflow(
    ws: WorkingState, *, parsed: ParsedFile,
    name: str, actors: list[str], systems: list[str],
    steps: list[str], manual_touchpoints: list[str], sources: list,
) -> dict:
    """Append one cited workflow record after validating its sources.

    Each source is round-tripped through the parser; invalid ones are dropped.
    The record is saved with only the kept sources when at least one survives;
    if none do, nothing is saved and ``ok`` is False with a corrective hint.
    """
    kept, dropped = _validate_sources(parsed, sources)
    if not kept:
        return {"ok": False, "dropped_sources": dropped, "hint": _NO_VALID_SOURCE_HINT}
    wf = WorkflowRecord(
        name=name, actors=actors, systems=systems, steps=steps,
        manual_touchpoints=manual_touchpoints,
        sources=[Source(**s) if isinstance(s, dict) else s for s in kept],
    )
    ws.workflows.append(wf)
    return {"ok": True, "workflow_index": len(ws.workflows) - 1, "dropped_sources": dropped}
