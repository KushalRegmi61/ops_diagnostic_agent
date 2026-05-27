"""Unit tests for the shared 'Operator priorities' block renderer."""
import pytest

from app.prompts._steering import Role, render_priorities_block
from app.schemas import RunContext


@pytest.mark.parametrize("role", list(Role))
def test_none_run_context_returns_empty(role):
    """No RunContext at all means empty string — caller can concatenate safely."""
    assert render_priorities_block(role=role, run_context=None) == ""


@pytest.mark.parametrize("role", list(Role))
def test_blank_steering_returns_empty(role):
    """has_steering()==False produces empty string, regardless of role."""
    ctx = RunContext(user_context="   ")
    assert render_priorities_block(role=role, run_context=ctx) == ""


def test_per_file_block_includes_recall_caveat():
    """The per-file block must explicitly preserve recall (search hint, not filter)."""
    ctx = RunContext(user_context="focus onboarding")
    block = render_priorities_block(role=Role.PER_FILE, run_context=ctx)
    assert "Operator priorities" in block
    assert "focus onboarding" in block
    lowered = block.lower()
    assert "still extract" in lowered or "do not drop" in lowered


def test_synthesis_block_weights_but_keeps_unrelated():
    ctx = RunContext(user_context="focus onboarding")
    block = render_priorities_block(role=Role.SYNTHESIS, run_context=ctx)
    assert "Operator priorities" in block
    assert "weight" in block.lower()
    assert "do not drop" in block.lower()


def test_ranking_block_is_a_tiebreak_not_a_filter():
    ctx = RunContext(user_context="focus onboarding")
    block = render_priorities_block(role=Role.RANKING, run_context=ctx)
    assert "tiebreak" in block.lower() or "rank" in block.lower()
    assert "do not omit" in block.lower() or "lower" in block.lower()


def test_selection_block_allows_priority_over_largest_roi():
    ctx = RunContext(user_context="focus onboarding")
    block = render_priorities_block(role=Role.SELECTION, run_context=ctx)
    assert "prefer" in block.lower()
    assert "largest roi" in block.lower() or "even if not the largest" in block.lower()


def test_framing_block_shapes_the_blueprint_around_priorities():
    ctx = RunContext(user_context="focus onboarding")
    block = render_priorities_block(role=Role.FRAMING, run_context=ctx)
    assert "frame" in block.lower()


def test_acceptance_block_is_fail_open():
    ctx = RunContext(user_context="focus onboarding")
    block = render_priorities_block(role=Role.ACCEPTANCE, run_context=ctx)
    assert "passed=false" in block.lower() or "set passed=false" in block.lower()
    assert "passed=true" in block.lower() or "default passed=true" in block.lower()


def test_block_starts_with_newline_for_safe_concatenation():
    """When non-empty, the block leads with a blank line so callers can `prompt + block + tail`."""
    ctx = RunContext(user_context="focus onboarding")
    block = render_priorities_block(role=Role.SYNTHESIS, run_context=ctx)
    assert block.startswith("\n\n")
