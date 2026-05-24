"""Lead node: first step of the diagnostic chain - identify workflows.

Re-derives a clean list of WorkflowRecord entries from the IntakeBundle so
that downstream bottleneck detection has a normalized workflow set to score
against.
"""
import json
import time

from pydantic import BaseModel

from app.agents.lead._logging import llm_meta_fields
from app.llm.base import LLMProvider
from app.prompts.workflow_map import PROMPT
from app.schemas import IntakeBundle, WorkflowRecord
from app.structured_logging import get_logger


logger = get_logger(__name__)


class _Wrap(BaseModel):
    """Schema wrapper so the LLM returns a JSON object with a ``workflows`` key."""
    workflows: list[WorkflowRecord]


def run(*, provider: LLMProvider, bundle: IntakeBundle) -> list[WorkflowRecord]:
    """Map workflows from the bundle; falls back to bundle.workflows on LLM failure."""
    started = time.perf_counter()
    logger.info("agent.lead.started", agent="workflow_map", bundle_workflow_count=len(bundle.workflows))
    prompt = PROMPT.format(bundle_json=json.dumps(bundle.model_dump(), indent=2))
    result, meta = provider.generate_json(prompt_name="workflow_map", prompt=prompt, schema=_Wrap)
    workflows = _Wrap.model_validate(result).workflows if result else bundle.workflows
    logger.info(
        "agent.lead.completed",
        agent="workflow_map",
        workflow_count=len(workflows),
        fallback="bundle_workflows" if not result else None,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        **llm_meta_fields(meta),
    )
    return workflows
