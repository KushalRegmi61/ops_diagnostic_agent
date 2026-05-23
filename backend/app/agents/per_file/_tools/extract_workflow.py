"""extract_workflow tool: append a WorkflowRecord to the WorkingState."""
from app.agents.per_file._state import WorkingState
from app.schemas import Source, WorkflowRecord


def extract_workflow(
    ws: WorkingState, *,
    name: str, actors: list[str], systems: list[str],
    steps: list[str], manual_touchpoints: list[str], sources: list[Source],
) -> dict:
    """Build a WorkflowRecord from the args, push it to ``ws.workflows``, return its index."""
    wf = WorkflowRecord(
        name=name, actors=actors, systems=systems, steps=steps,
        manual_touchpoints=manual_touchpoints, sources=sources,
    )
    ws.workflows.append(wf)
    return {"ok": True, "workflow_index": len(ws.workflows) - 1}
