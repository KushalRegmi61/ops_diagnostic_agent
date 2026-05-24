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
from app.schemas import Source, WorkflowRecord


def extract_workflow(
    ws: WorkingState, *,
    name: str, actors: list[str], systems: list[str],
    steps: list[str], manual_touchpoints: list[str], sources: list[Source],
) -> dict:
    """Append one cited workflow/process record to ``ws.workflows``.

    ``name`` should be a concise process name. ``actors`` are people or roles.
    ``systems`` are tools/apps/documents involved. ``steps`` are the observed
    sequence of work. ``manual_touchpoints`` are places where humans copy,
    chase, reconcile, re-key, or wait. ``sources`` must cite the evidence.

    Returns a small acknowledgement containing the inserted workflow index.
    """
    wf = WorkflowRecord(
        name=name, actors=actors, systems=systems, steps=steps,
        manual_touchpoints=manual_touchpoints, sources=sources,
    )
    ws.workflows.append(wf)
    return {"ok": True, "workflow_index": len(ws.workflows) - 1}
