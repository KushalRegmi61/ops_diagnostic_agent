from app.agents.per_file._state import WorkingState
from app.schemas import FileSummary


def finalize_summary(ws: WorkingState, *, one_paragraph_summary: str, open_questions: list[str] | None = None) -> FileSummary:
    return FileSummary(
        file_id=ws.file_id,
        file_name=ws.file_name,
        one_paragraph_summary=one_paragraph_summary,
        key_workflows=ws.workflows,
        key_pain_signals=ws.pain_signals,
        lead_rows=ws.lead_rows,
        open_questions=open_questions or ws.open_questions,
        agent_notes=ws.notes,
    )
