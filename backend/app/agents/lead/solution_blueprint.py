"""Lead node: write the final cited automation Blueprint.

Fifth and final step of the diagnostic chain. Produces a Blueprint with
``summary``, ``steps``, ``required_systems``, ``success_metrics``, and
``risks`` - each carrying Sources whose locators must round-trip through
``app.parsers.excerpt``. Accepts an optional ``revision_detail`` so the
bounded revision loop can re-emit a corrected blueprint after self-review.
"""
import json

from app.llm.base import LLMProvider
from app.prompts.solution_blueprint import PROMPT
from app.schemas import Blueprint, IntakeBundle, Opportunity


def run(
    *,
    provider: LLMProvider,
    bundle: IntakeBundle,
    selected: Opportunity,
    selected_index: int,
    revision_detail: str | None = None,
) -> Blueprint | None:
    """Generate the Blueprint via one LLM call; appends a fix-it preamble when revising."""
    prompt = PROMPT.format(
        selected_index=selected_index,
        selected_json=json.dumps(selected.model_dump(), indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    if revision_detail:
        prompt += f"\n\nThe previous blueprint failed self-review: {revision_detail}. Fix it."
    result, _ = provider.generate_json(prompt_name="solution_blueprint", prompt=prompt, schema=Blueprint)
    return Blueprint.model_validate(result) if result else None
