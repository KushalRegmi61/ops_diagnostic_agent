"""Lead node: score opportunities from bottlenecks by ROI.

Third step of the diagnostic chain. Turns each Bottleneck into an Opportunity
with ``roi_score``, ``effort_score``, ``risk_score``, and ``pain_score`` so
downstream selection can pick the fastest win.
"""
import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.roi_score import PROMPT
from app.schemas import Bottleneck, IntakeBundle, Opportunity


class _Wrap(BaseModel):
    """Schema wrapper so the LLM returns a JSON object with an ``opportunities`` key."""
    opportunities: list[Opportunity]


def run(*, provider: LLMProvider, bundle: IntakeBundle, bottlenecks: list[Bottleneck]) -> list[Opportunity]:
    """Score ROI for each bottleneck via one LLM call; returns an empty list on parse failure."""
    prompt = PROMPT.format(
        bottlenecks_json=json.dumps([b.model_dump() for b in bottlenecks], indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    result, _ = provider.generate_json(prompt_name="roi_score", prompt=prompt, schema=_Wrap)
    return _Wrap.model_validate(result).opportunities if result else []
