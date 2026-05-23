"""Lead node: pick the single highest-ROI, lowest-effort opportunity.

Fourth step of the diagnostic chain. Returns one Opportunity (or None when
the list is empty). Falls back to a deterministic ``roi - effort - risk``
ranking when the LLM cannot produce a valid index.
"""
import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.fastest_win_select import PROMPT
from app.schemas import Opportunity


class _Wrap(BaseModel):
    """Schema wrapper carrying the LLM's chosen index into the opportunities list."""
    selected_index: int


def run(*, provider: LLMProvider, opportunities: list[Opportunity]) -> Opportunity | None:
    """Select the fastest-win opportunity; deterministic sort fallback when the LLM fails or returns OOB."""
    if not opportunities:
        return None
    prompt = PROMPT.format(opportunities_json=json.dumps([o.model_dump() for o in opportunities], indent=2))
    result, _ = provider.generate_json(prompt_name="fastest_win_select", prompt=prompt, schema=_Wrap)
    if not result:
        # Deterministic fallback.
        opportunities_sorted = sorted(
            opportunities,
            key=lambda o: (o.roi_score - o.effort_score - o.risk_score, o.pain_score, -o.effort_score),
            reverse=True,
        )
        return opportunities_sorted[0]
    idx = _Wrap.model_validate(result).selected_index
    if 0 <= idx < len(opportunities):
        return opportunities[idx]
    return opportunities[0]
