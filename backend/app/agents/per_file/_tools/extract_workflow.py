from app.agents.per_file._state import WorkingState
from app.schemas import Source, WorkflowRecord


def extract_workflow(
    ws: WorkingState, *,
    name: str, actors: list[str], systems: list[str],
    steps: list[str], manual_touchpoints: list[str], sources: list[Source],
) -> dict:
    wf = WorkflowRecord(
        name=name, actors=actors, systems=systems, steps=steps,
        manual_touchpoints=manual_touchpoints, sources=sources,
    )
    ws.workflows.append(wf)
    return {"ok": True, "workflow_index": len(ws.workflows) - 1}
