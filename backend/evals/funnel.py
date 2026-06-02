"""Per-file extraction funnel for the failure diagnostic.

Counts the search→hit→read→cite→round-trip→extract pipeline from the tool calls
the per-file loop replays through ``on_tool_call``, derives the loop's terminal
path from the returned summary, and classifies where extraction collapsed.
"""
from pydantic import BaseModel

from app.schemas import FileSummary

_EXTRACT_TOOLS = {"extract_workflow", "extract_pain_signal", "extract_lead_row"}
_FORCE_NOTE = "force-finalized on saturation/budget"


class RunFunnel(BaseModel):
    """Stage counts for one per-file run; terminal_reason is stamped after the run."""

    searches_issued: int = 0
    search_hits_returned: int = 0
    reads_issued: int = 0
    cite_calls: int = 0
    cite_round_trips: int = 0
    extract_calls: int = 0
    terminal_reason: str = "unknown"


class FunnelCollector:
    """``on_tool_call`` sink that tallies the extraction funnel for one run."""

    def __init__(self) -> None:
        """Start an empty funnel."""
        self.funnel = RunFunnel()

    def __call__(self, name: str, args: dict, result: object) -> None:
        """Fold one replayed tool call + result into the funnel counts."""
        f = self.funnel
        if name == "search_text":
            f.searches_issued += 1
            if isinstance(result, list):
                f.search_hits_returned += len(result)
        elif name == "read_segment":
            f.reads_issued += 1
        elif name == "cite_locator":
            f.cite_calls += 1
            if isinstance(result, dict) and result.get("valid") is True:
                f.cite_round_trips += 1
        elif name in _EXTRACT_TOOLS:
            f.extract_calls += 1


def terminal_reason(summary: FileSummary) -> str:
    """Derive the loop's terminal path from the returned FileSummary shape.

    Returns one of: fallback | force_finalize | model_finalize.
    """
    if summary.one_paragraph_summary.startswith("(partial"):
        return "fallback"
    if _FORCE_NOTE in (summary.agent_notes or ""):
        return "force_finalize"
    return "model_finalize"
