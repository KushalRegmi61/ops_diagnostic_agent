"""Lead node: score opportunities from bottlenecks by ROI.

Third step of the diagnostic chain. Turns each Bottleneck into an Opportunity
with ``roi_score``, ``effort_score``, ``risk_score``, and ``pain_score`` so
downstream selection can pick the fastest win.
"""
import json
import time

from pydantic import BaseModel

from app.agents.lead._logging import llm_meta_fields
from app.llm.base import LLMParseError, LLMProvider
from app.prompts.roi_score import PROMPT
from app.schemas import Bottleneck, IntakeBundle, Opportunity
from app.structured_logging import get_logger


logger = get_logger(__name__)


class _Wrap(BaseModel):
    """Schema wrapper so the LLM returns a JSON object with an ``opportunities`` key."""
    opportunities: list[Opportunity]


def run(*, provider: LLMProvider, bundle: IntakeBundle, bottlenecks: list[Bottleneck]) -> list[Opportunity]:
    """Score ROI for each bottleneck via one LLM call; returns an empty list on parse failure."""
    started = time.perf_counter()
    logger.info("agent.lead.started", agent="roi_score", bottleneck_count=len(bottlenecks))
    prompt = PROMPT.format(
        bottlenecks_json=json.dumps([b.model_dump() for b in bottlenecks], indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    result, meta = provider.generate_json(prompt_name="roi_score", prompt=prompt, schema=_Wrap)
    if not meta.parsed_json:
        raise LLMParseError(
            stage="roi_score",
            message=f"provider returned parsed_json=False after {meta.retry_count} retries",
        )
    opportunities = _Wrap.model_validate(result).opportunities
    logger.info(
        "agent.lead.completed",
        agent="roi_score",
        opportunity_count=len(opportunities),
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        **llm_meta_fields(meta),
    )
    return opportunities
