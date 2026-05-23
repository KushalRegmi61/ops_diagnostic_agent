import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.fastest_win_select import PROMPT
from app.schemas import Opportunity


class _Wrap(BaseModel):
    selected_index: int


def run(*, provider: LLMProvider, opportunities: list[Opportunity]) -> Opportunity | None:
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
