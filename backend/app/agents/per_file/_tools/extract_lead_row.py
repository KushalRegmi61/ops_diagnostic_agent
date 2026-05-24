"""Tool for capturing one lead/contact/opportunity record from a parsed file.

The per-file ReAct agent calls ``extract_lead_row`` after it has read a segment
that looks like a structured business record: a CSV row, XLSX row, JSON object,
or email/contact payload. This tool does not search or interpret the file by
itself; it records the LLM's extracted row into ``WorkingState.lead_rows`` so
later lead-level agents can reason across all discovered pipeline records.

A LeadRow has three parts:
- ``raw``: the original field names and values as they appeared in the source.
- ``normalized``: cleaned, consistent keys/values for downstream analysis.
- ``source``: the exact cited file locator where this row came from.

Example:
    raw = {"Lead Name": "Acme Inc", "Status": "New", "Owner": ""}
    normalized = {"lead_name": "Acme Inc", "status": "new", "owner": None}
    source = Source(... locator={"type": "table", "row_index": 4})

Use this tool for evidence records, not for conclusions. If the row reveals a
problem such as no owner, stale follow-up, or missing email, the agent should
also call ``extract_pain_signal`` with the same source.
"""
from app.agents.per_file._state import WorkingState
from app.schemas import LeadRow, Source


def extract_lead_row(ws: WorkingState, *, raw: dict, normalized: dict, source: Source) -> dict:
    """Append one cited lead-like record to the working state.

    ``raw`` preserves the source record exactly enough for audit/review.
    ``normalized`` converts that record into stable keys such as
    ``company``, ``contact_name``, ``email``, ``stage``, ``owner``,
    ``last_contact_date``, or ``estimated_value`` when those fields exist.
    ``source`` must point to the row/object/message segment that supports the
    extraction, ideally after the agent has validated the locator.

    Returns a small acknowledgement containing the inserted row index.
    """
    lr = LeadRow(raw=raw, normalized=normalized, source=source)
    ws.lead_rows.append(lr)
    return {"ok": True, "lead_row_index": len(ws.lead_rows) - 1}
