"""Unit tests for the RunContext Pydantic model."""
import pytest
from pydantic import ValidationError

from app.schemas import RunContext


def test_default_has_no_steering():
    """An empty RunContext reports no steering present."""
    assert RunContext().has_steering() is False


def test_blank_user_context_has_no_steering():
    """Whitespace-only user_context is treated as absent steering."""
    assert RunContext(user_context="   \n\t").has_steering() is False


def test_none_user_context_has_no_steering():
    """Explicit None user_context is absent steering."""
    assert RunContext(user_context=None).has_steering() is False


def test_populated_user_context_has_steering():
    """Non-empty user_context flips has_steering() True."""
    assert RunContext(user_context="focus onboarding").has_steering() is True


def test_rejects_oversize_user_context():
    """user_context above 2000 chars raises ValidationError at construction."""
    with pytest.raises(ValidationError):
        RunContext(user_context="x" * 2001)


def test_accepts_exact_cap():
    """Exactly 2000 chars is accepted."""
    ctx = RunContext(user_context="x" * 2000)
    assert ctx.has_steering() is True


def test_roundtrips_through_json():
    """RunContext model_dump_json → model_validate_json preserves value."""
    original = RunContext(user_context="focus onboarding")
    restored = RunContext.model_validate_json(original.model_dump_json())
    assert restored == original
