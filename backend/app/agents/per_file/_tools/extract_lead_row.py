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
from app.agents.per_file._tools._citation import _validate_sources
from app.schemas import KVPair, LeadRow, ParsedFile, Source

_INVALID_SOURCE_HINT = (
    "source failed to round-trip — re-check the locator against the segment index"
)


def _to_kv_pairs(d: dict | list) -> list[KVPair]:
    """Coerce a free-form dict (or pre-built KV list) into ``list[KVPair]`` with stringified values."""
    if isinstance(d, list):
        return [item if isinstance(item, KVPair) else KVPair(**item) for item in d]
    return [KVPair(key=str(k), value="" if v is None else str(v)) for k, v in d.items()]


def extract_lead_row(ws: WorkingState, *, parsed: ParsedFile, raw: dict, normalized: dict, source) -> dict:
    """Append one cited lead-like record after validating its single source.

    If the source round-trips, the row is saved; otherwise nothing is saved and
    ``ok`` is False with a corrective hint.
    """
    kept, _dropped = _validate_sources(parsed, [source])
    if not kept:
        return {"ok": False, "hint": _INVALID_SOURCE_HINT}
    src = Source(**kept[0]) if isinstance(kept[0], dict) else kept[0]
    lr = LeadRow(raw=_to_kv_pairs(raw), normalized=_to_kv_pairs(normalized), source=src)
    ws.lead_rows.append(lr)
    return {"ok": True, "lead_row_index": len(ws.lead_rows) - 1}
