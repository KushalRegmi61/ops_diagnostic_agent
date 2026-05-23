import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.bottleneck_detect import PROMPT
from app.schemas import Bottleneck, IntakeBundle, WorkflowRecord


class _Wrap(BaseModel):
    bottlenecks: list[Bottleneck]


def run(*, provider: LLMProvider, bundle: IntakeBundle, workflows: list[WorkflowRecord]) -> list[Bottleneck]:
    prompt = PROMPT.format(
        workflows_json=json.dumps([w.model_dump() for w in workflows], indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    result, _ = provider.generate_json(prompt_name="bottleneck_detect", prompt=prompt, schema=_Wrap)
    return _Wrap.model_validate(result).bottlenecks if result else []
