"""Lead node: write the final cited automation Blueprint.

Fifth and final step of the diagnostic chain. Produces a Blueprint with
``summary``, ``steps``, ``required_systems``, ``success_metrics``, and
``risks`` - each carrying Sources whose locators must round-trip through
``app.parsers.excerpt``. Accepts an optional ``revision_detail`` so the
bounded revision loop can re-emit a corrected blueprint after self-review.
"""
import json
import time

from app.agents.lead._logging import llm_meta_fields
from app.llm.base import LLMProvider
from app.prompts.solution_blueprint import PROMPT
from app.schemas import Blueprint, IntakeBundle, Opportunity
from app.structured_logging import get_logger


logger = get_logger(__name__)


def run(
    *,
    provider: LLMProvider,
    bundle: IntakeBundle,
    selected: Opportunity,
    selected_index: int,
    revision_detail: str | None = None,
) -> Blueprint | None:
    """Generate the Blueprint via one LLM call; appends a fix-it preamble when revising."""
    started = time.perf_counter()
    logger.info(
        "agent.lead.started",
        agent="solution_blueprint",
        selected_index=selected_index,
        revision=bool(revision_detail),
        workflow_count=len(bundle.workflows),
        pain_signal_count=len(bundle.pain_signals),
    )
    prompt = PROMPT.format(
        selected_index=selected_index,
        selected_json=json.dumps(selected.model_dump(), indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    if revision_detail:
        prompt += f"\n\nThe previous blueprint failed self-review: {revision_detail}. Fix it."
    result, meta = provider.generate_json(prompt_name="solution_blueprint", prompt=prompt, schema=Blueprint)
    blueprint = Blueprint.model_validate(result) if result else None
    logger.info(
        "agent.lead.completed",
        agent="solution_blueprint",
        has_blueprint=blueprint is not None,
        step_count=len(blueprint.steps) if blueprint is not None else 0,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        **llm_meta_fields(meta),
    )
    return blueprint
