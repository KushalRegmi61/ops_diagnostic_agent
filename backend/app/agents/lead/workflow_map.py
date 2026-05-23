import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.workflow_map import PROMPT
from app.schemas import IntakeBundle, WorkflowRecord


class _Wrap(BaseModel):
    workflows: list[WorkflowRecord]


def run(*, provider: LLMProvider, bundle: IntakeBundle) -> list[WorkflowRecord]:
    prompt = PROMPT.format(bundle_json=json.dumps(bundle.model_dump(), indent=2))
    result, _ = provider.generate_json(prompt_name="workflow_map", prompt=prompt, schema=_Wrap)
    return _Wrap.model_validate(result).workflows if result else bundle.workflows
