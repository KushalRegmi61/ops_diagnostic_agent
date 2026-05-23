from app.agents.per_file._state import WorkingState
from app.schemas import LeadRow, Source


def extract_lead_row(ws: WorkingState, *, raw: dict, normalized: dict, source: Source) -> dict:
    lr = LeadRow(raw=raw, normalized=normalized, source=source)
    ws.lead_rows.append(lr)
    return {"ok": True, "lead_row_index": len(ws.lead_rows) - 1}
