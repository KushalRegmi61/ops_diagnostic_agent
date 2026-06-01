"""Plan-first checklist for the per-file ReAct loop.

One structured ``generate_json`` call before the loop produces a 2-4 item plan
the agent exhausts (Plan-and-Solve). Degrades to a static default checklist on
any failure -- logged, never silent -- so the loop always has a termination target.
"""
from pydantic import BaseModel, field_validator

from app.llm.base import LLMProvider
from app.schemas import ParsedFile
from app.structured_logging import get_logger

logger = get_logger(__name__)

DEFAULT_PLAN = [
    "search for the main workflows in this file",
    "search for operational pain signals",
    "cite locators and extract the strongest findings",
    "finalize the summary",
]

_PLAN_PROMPT = (
    "You are planning how to extract cited findings from one operational file.\n"
    "File: {file_name} (type={file_type}, {segment_count} segments).\n"
    "Produce a SHORT ordered checklist of 2-4 high-level steps you will follow to "
    "find workflows, pain signals, and lead rows, then finalize. Keep each step to a "
    "few words. Do not reference specific content you have not seen yet."
)


class PlanChecklist(BaseModel):
    """A 2-4 item ordered plan the agent exhausts to define 'done'."""
    items: list[str]

    @field_validator("items")
    @classmethod
    def _clamp(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s and s.strip()]
        if len(cleaned) < 2:
            cleaned = (cleaned + DEFAULT_PLAN)[:2]
        return cleaned[:4]


def make_plan(provider: LLMProvider, parsed: ParsedFile) -> list[str]:
    """Run the plan-first call; return its items, or DEFAULT_PLAN on any failure."""
    prompt = _PLAN_PROMPT.format(
        file_name=parsed.file_name, file_type=parsed.type, segment_count=len(parsed.segments)
    )
    try:
        data, _meta = provider.generate_json(  # type: ignore[attr-defined]
            prompt_name=f"per_file_plan_{parsed.type}", prompt=prompt, schema=PlanChecklist
        )
        return PlanChecklist.model_validate(data).items
    except Exception as exc:  # degrade, but surface the reason
        logger.warning("agent.per_file.plan_fallback", file_id=parsed.file_id, error=str(exc))
        return list(DEFAULT_PLAN)
