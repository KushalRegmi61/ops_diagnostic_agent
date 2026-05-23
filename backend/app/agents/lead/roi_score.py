import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.roi_score import PROMPT
from app.schemas import Bottleneck, IntakeBundle, Opportunity


class _Wrap(BaseModel):
    opportunities: list[Opportunity]


def run(*, provider: LLMProvider, bundle: IntakeBundle, bottlenecks: list[Bottleneck]) -> list[Opportunity]:
    prompt = PROMPT.format(
        bottlenecks_json=json.dumps([b.model_dump() for b in bottlenecks], indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    result, _ = provider.generate_json(prompt_name="roi_score", prompt=prompt, schema=_Wrap)
    return _Wrap.model_validate(result).opportunities if result else []
