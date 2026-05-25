"""Prompt-stack coverage for lead and per-file agent prompts."""

import pytest

from app.agents.per_file import docx, json, markdown, mbox, pdf, table, transcript
from app.prompts import (
    bottleneck_detect,
    fastest_win_select,
    review_summaries,
    roi_score,
    self_review_final,
    solution_blueprint,
    synthesis,
    workflow_map,
)


REQUIRED_LABELS = [
    "Act as",
    "Your task is",
    "You already have:",
    "Output schema:",
    "Example:",
    "Format:",
    "Constraints:",
]

PROMPT_CASES = [
    (review_summaries.PROMPT, ["summaries_json"]),
    (synthesis.PROMPT, ["summaries_json"]),
    (workflow_map.PROMPT, ["bundle_json"]),
    (bottleneck_detect.PROMPT, ["workflows_json", "bundle_json"]),
    (roi_score.PROMPT, ["bottlenecks_json", "bundle_json"]),
    (fastest_win_select.PROMPT, ["opportunities_json"]),
    (solution_blueprint.PROMPT, ["selected_index", "selected_json", "bundle_json"]),
    (self_review_final.PROMPT, ["blueprint_json", "selected_json", "opportunities_json", "open_questions_json"]),
]

FORMAT_VALUES = {
    "summaries_json": "{}",
    "bundle_json": "{}",
    "workflows_json": "[]",
    "bottlenecks_json": "[]",
    "opportunities_json": "[]",
    "selected_index": 0,
    "selected_json": "{}",
    "blueprint_json": "{}",
    "open_questions_json": "[]",
}


def _assert_template_order(prompt: str) -> None:
    """Assert schema-first template labels appear in the required order."""
    positions = [prompt.index(section) for section in REQUIRED_LABELS]
    assert positions == sorted(positions)


@pytest.mark.parametrize(("prompt", "placeholders"), PROMPT_CASES)
def test_lead_prompts_use_prompt_stack_and_preserve_placeholders(prompt: str, placeholders: list[str]):
    """Every lead prompt keeps schema-first order, strict JSON output, and required placeholders."""
    _assert_template_order(prompt)
    assert "Reply ONLY with JSON" in prompt
    for placeholder in placeholders:
        assert "{" + placeholder + "}" in prompt


@pytest.mark.parametrize(("prompt", "placeholders"), PROMPT_CASES)
def test_lead_prompts_format_with_minimal_json(prompt: str, placeholders: list[str]):
    """Prompt examples and braces remain compatible with str.format."""
    rendered = prompt.format(**FORMAT_VALUES)

    assert "{" not in rendered or "}" in rendered
    for placeholder in placeholders:
        assert "{" + placeholder + "}" not in rendered


def test_only_solution_blueprint_declares_tone():
    """Only the user-facing blueprint prompt needs tone guidance."""
    for prompt, _placeholders in PROMPT_CASES:
        if prompt is solution_blueprint.PROMPT:
            assert "Tone:" in prompt
        else:
            assert "Tone:" not in prompt


def test_solution_blueprint_prompt_demands_depth():
    """Blueprint prompt asks for research-depth output, not one-line claims."""
    prompt = solution_blueprint.PROMPT

    assert "100-200 words" in prompt
    assert "5-8 ordered implementation steps" in prompt
    assert "2-4 sentences" in prompt
    assert "Technical requirements" in prompt
    assert "auth/permissions" in prompt
    assert "baseline/target" in prompt
    assert "Avoid shallow one-line claims" in prompt


@pytest.mark.parametrize(
    "suffix",
    [pdf._SUFFIX, docx._SUFFIX, markdown._SUFFIX, transcript._SUFFIX, table._SUFFIX, mbox._SUFFIX, json._SUFFIX],
)
def test_per_file_suffixes_are_concise_locator_guidance(suffix: str):
    """Per-file suffixes add only file-type evidence and locator guidance."""
    assert "Locator" in suffix or "Locators" in suffix
    assert "Reply ONLY" not in suffix
    assert "Persona" not in suffix
    assert len(suffix.split()) <= 30
