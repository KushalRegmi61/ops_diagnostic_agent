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


def test_solution_blueprint_prompt_demands_concise_markdown():
    """Blueprint prompt asks for terse bold-lead markdown, not prose paragraphs."""
    prompt = solution_blueprint.PROMPT

    assert "≤40 words" in prompt
    assert "≤80 words" in prompt
    assert "bold lead" in prompt.lower()
    assert "Avoid prose paragraphs" in prompt
    assert "Avoid restating context across claims" in prompt
    # citation invariants preserved
    assert "Avoid bare source strings" in prompt
    assert "Avoid hallucinating" in prompt


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


def test_render_brief_without_user_context_omits_priorities_block():
    """No steering → the brief contains no 'Operator priorities' header."""
    from app.prompts.per_file_brief import render_brief
    brief = render_brief(
        file_id="f1", file_name="x.txt", file_type="txt",
        segment_count=3, iteration_cap=6,
    )
    assert "Operator priorities" not in brief


def test_render_brief_with_blank_user_context_omits_block():
    """Whitespace-only user_context behaves like None."""
    from app.prompts.per_file_brief import render_brief
    brief = render_brief(
        file_id="f1", file_name="x.txt", file_type="txt",
        segment_count=3, iteration_cap=6,
        user_context="   ",
    )
    assert "Operator priorities" not in brief


def test_render_brief_with_user_context_includes_priorities_block():
    """A populated user_context renders the per-file priorities block (with recall caveat)."""
    from app.prompts.per_file_brief import render_brief
    brief = render_brief(
        file_id="f1", file_name="x.txt", file_type="txt",
        segment_count=3, iteration_cap=6,
        user_context="focus onboarding",
    )
    assert "Operator priorities" in brief
    assert "focus onboarding" in brief
    # recall caveat from PER_FILE role
    assert "Still extract" in brief


def test_synthesis_render_without_context_matches_baseline():
    """render(run_context=None) is byte-identical to PROMPT.format(...) — baseline preserved."""
    from app.prompts import synthesis as synth_prompt
    baseline = synth_prompt.PROMPT.format(summaries_json="{}")
    rendered = synth_prompt.render(run_context=None, summaries_json="{}")
    assert rendered == baseline


def test_synthesis_render_with_blank_context_matches_baseline():
    """Whitespace-only steering is treated as absent — byte-identical baseline."""
    from app.prompts import synthesis as synth_prompt
    from app.schemas import RunContext
    baseline = synth_prompt.PROMPT.format(summaries_json="{}")
    rendered = synth_prompt.render(
        run_context=RunContext(user_context="   "),
        summaries_json="{}",
    )
    assert rendered == baseline


def test_synthesis_render_with_steering_appends_priorities_block():
    """Populated steering appends the SYNTHESIS role's priorities block."""
    from app.prompts import synthesis as synth_prompt
    from app.schemas import RunContext
    ctx = RunContext(user_context="focus onboarding")
    rendered = synth_prompt.render(run_context=ctx, summaries_json="{}")
    assert "Operator priorities" in rendered
    assert "focus onboarding" in rendered
    assert "do not drop" in rendered.lower()


def _bd_kwargs():
    """Sample format kwargs matching bottleneck_detect.PROMPT placeholders."""
    return {"bundle_json": "{}", "workflows_json": "[]"}


def test_bottleneck_detect_render_without_context_matches_baseline():
    """Baseline byte-identity: no steering → output equals PROMPT.format(...)."""
    from app.prompts import bottleneck_detect as bd_prompt
    baseline = bd_prompt.PROMPT.format(**_bd_kwargs())
    rendered = bd_prompt.render(run_context=None, **_bd_kwargs())
    assert rendered == baseline


def test_bottleneck_detect_render_with_blank_context_matches_baseline():
    """Whitespace-only steering → still byte-identical baseline."""
    from app.prompts import bottleneck_detect as bd_prompt
    from app.schemas import RunContext
    baseline = bd_prompt.PROMPT.format(**_bd_kwargs())
    rendered = bd_prompt.render(
        run_context=RunContext(user_context="   "),
        **_bd_kwargs(),
    )
    assert rendered == baseline


def test_bottleneck_detect_render_with_steering_uses_ranking_role():
    """Populated steering → appends RANKING-role block (tiebreak phrasing)."""
    from app.prompts import bottleneck_detect as bd_prompt
    from app.schemas import RunContext
    ctx = RunContext(user_context="focus onboarding")
    rendered = bd_prompt.render(run_context=ctx, **_bd_kwargs())
    assert "Operator priorities" in rendered
    lowered = rendered.lower()
    assert "tiebreak" in lowered or "rank" in lowered
    assert "do not omit" in lowered or "lower" in lowered


def _fw_kwargs():
    """Sample format kwargs for fastest_win_select."""
    return {"opportunities_json": "[]"}


def test_fastest_win_select_render_without_context_matches_baseline():
    """Baseline byte-identity preserved when no steering."""
    from app.prompts import fastest_win_select as fw_prompt
    assert fw_prompt.render(run_context=None, **_fw_kwargs()) == fw_prompt.PROMPT.format(**_fw_kwargs())


def test_fastest_win_select_render_with_blank_context_matches_baseline():
    """Whitespace-only steering → baseline byte-identity."""
    from app.prompts import fastest_win_select as fw_prompt
    from app.schemas import RunContext
    assert fw_prompt.render(
        run_context=RunContext(user_context="   "),
        **_fw_kwargs(),
    ) == fw_prompt.PROMPT.format(**_fw_kwargs())


def test_fastest_win_select_render_with_steering_uses_selection_role():
    """Populated steering → SELECTION-role block: 'prefer' + 'largest ROI'."""
    from app.prompts import fastest_win_select as fw_prompt
    from app.schemas import RunContext
    ctx = RunContext(user_context="focus onboarding")
    rendered = fw_prompt.render(run_context=ctx, **_fw_kwargs())
    assert "Operator priorities" in rendered
    lowered = rendered.lower()
    assert "prefer" in lowered
    assert "largest roi" in lowered or "even if not the largest" in lowered


def _sb_kwargs():
    """Sample format kwargs for solution_blueprint."""
    return {"bundle_json": "{}", "selected_index": 0, "selected_json": "{}"}


def test_solution_blueprint_render_without_context_matches_baseline():
    """Baseline byte-identity preserved when no steering."""
    from app.prompts import solution_blueprint as sb_prompt
    assert sb_prompt.render(run_context=None, **_sb_kwargs()) == sb_prompt.PROMPT.format(**_sb_kwargs())


def test_solution_blueprint_render_with_blank_context_matches_baseline():
    """Whitespace-only steering → baseline byte-identity."""
    from app.prompts import solution_blueprint as sb_prompt
    from app.schemas import RunContext
    assert sb_prompt.render(
        run_context=RunContext(user_context="   "),
        **_sb_kwargs(),
    ) == sb_prompt.PROMPT.format(**_sb_kwargs())


def test_solution_blueprint_render_with_steering_uses_framing_role():
    """Populated steering → FRAMING-role block: 'frame'."""
    from app.prompts import solution_blueprint as sb_prompt
    from app.schemas import RunContext
    ctx = RunContext(user_context="focus onboarding")
    rendered = sb_prompt.render(run_context=ctx, **_sb_kwargs())
    assert "Operator priorities" in rendered
    assert "frame" in rendered.lower()


def _srf_kwargs():
    """Sample format kwargs for self_review_final."""
    return {
        "blueprint_json": "{}",
        "open_questions_json": "[]",
        "opportunities_json": "[]",
        "selected_json": "{}",
    }


def test_self_review_final_render_without_context_matches_baseline():
    """Baseline byte-identity preserved when no steering."""
    from app.prompts import self_review_final as srf_prompt
    assert srf_prompt.render(run_context=None, **_srf_kwargs()) == srf_prompt.PROMPT.format(**_srf_kwargs())


def test_self_review_final_render_with_blank_context_matches_baseline():
    """Whitespace-only steering → baseline byte-identity."""
    from app.prompts import self_review_final as srf_prompt
    from app.schemas import RunContext
    assert srf_prompt.render(
        run_context=RunContext(user_context="   "),
        **_srf_kwargs(),
    ) == srf_prompt.PROMPT.format(**_srf_kwargs())


def test_self_review_final_render_with_steering_uses_acceptance_role():
    """Populated steering → ACCEPTANCE-role block: fail-open ('passed=false' AND 'passed=true')."""
    from app.prompts import self_review_final as srf_prompt
    from app.schemas import RunContext
    ctx = RunContext(user_context="focus onboarding")
    rendered = srf_prompt.render(run_context=ctx, **_srf_kwargs())
    assert "Operator priorities" in rendered
    lowered = rendered.lower()
    assert "passed=false" in lowered
    assert "passed=true" in lowered  # fail-open clause
