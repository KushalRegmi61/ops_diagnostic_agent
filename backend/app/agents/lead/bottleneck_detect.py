"""Lead node: detect bottlenecks per workflow.

Second step of the five-node diagnostic chain. Consumes the workflows from
``workflow_map`` together with the full IntakeBundle (for pain signals and
contradictions) and returns a list of Bottleneck objects with cited sources.
"""
import json
import time

from pydantic import BaseModel

from app.agents.lead._logging import llm_meta_fields
from app.llm.base import LLMParseError, LLMProvider
from app.prompts.bottleneck_detect import PROMPT
from app.schemas import Bottleneck, IntakeBundle, WorkflowRecord
from app.structured_logging import get_logger


logger = get_logger(__name__)


class _Wrap(BaseModel):
    """Schema wrapper so the LLM returns a JSON object with a ``bottlenecks`` key."""
    bottlenecks: list[Bottleneck]


def run(*, provider: LLMProvider, bundle: IntakeBundle, workflows: list[WorkflowRecord]) -> list[Bottleneck]:
    """Detect bottlenecks via one LLM call; returns an empty list on parse failure."""
    started = time.perf_counter()
    logger.info(
        "agent.lead.started",
        agent="bottleneck_detect",
        workflow_count=len(workflows),
        pain_signal_count=len(bundle.pain_signals),
    )
    prompt = PROMPT.format(
        workflows_json=json.dumps([w.model_dump() for w in workflows], indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    result, meta = provider.generate_json(prompt_name="bottleneck_detect", prompt=prompt, schema=_Wrap)
    if not meta.parsed_json:
        raise LLMParseError(
            stage="bottleneck_detect",
            message=f"provider returned parsed_json=False after {meta.retry_count} retries",
        )
    bottlenecks = _Wrap.model_validate(result).bottlenecks
    logger.info(
        "agent.lead.completed",
        agent="bottleneck_detect",
        bottleneck_count=len(bottlenecks),
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        **llm_meta_fields(meta),
    )
    return bottlenecks
