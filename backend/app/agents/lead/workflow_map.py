"""Lead node: first step of the diagnostic chain - identify workflows.

Re-derives a clean list of WorkflowRecord entries from the IntakeBundle so
that downstream bottleneck detection has a normalized workflow set to score
against.
"""
import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.workflow_map import PROMPT
from app.schemas import IntakeBundle, WorkflowRecord


class _Wrap(BaseModel):
    """Schema wrapper so the LLM returns a JSON object with a ``workflows`` key."""
    workflows: list[WorkflowRecord]


def run(*, provider: LLMProvider, bundle: IntakeBundle) -> list[WorkflowRecord]:
    """Map workflows from the bundle; falls back to bundle.workflows on LLM failure."""
    prompt = PROMPT.format(bundle_json=json.dumps(bundle.model_dump(), indent=2))
    result, _ = provider.generate_json(prompt_name="workflow_map", prompt=prompt, schema=_Wrap)
    return _Wrap.model_validate(result).workflows if result else bundle.workflows
