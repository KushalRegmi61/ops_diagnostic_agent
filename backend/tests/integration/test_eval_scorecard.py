"""Skip-gated scorecard gate. Records the Increment #1 baseline and asserts a floor.

Run once on this branch BEFORE Phase B to capture the baseline numbers, then keep
as the regression gate Phase B (and #2/#3) must clear.
"""
import pytest

from app.config import get_settings
from app.llm import get_provider
from evals.scorecard import run_scorecard


def _provider_up() -> bool:
    """True when the configured provider is constructible."""
    try:
        settings = get_settings()
        provider = get_provider()
        return provider is not None and bool(settings.llm_provider)
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _provider_up(), reason="LLM provider not reachable")


def test_scorecard_meets_increment1_floor():
    """Run the scorecard over the corpus and assert the pinned Increment #1 floor."""
    get_provider.cache_clear()
    card = run_scorecard(get_provider())
    # Print the full scorecard so the baseline numbers are captured in test output.
    print("\nSCORECARD:", card.model_dump_json(indent=2))
    # Baseline recorded 2026-06-01 (Increment #1, gpt-5.4-nano): convergence=0.33, citation_round_trip=0.33, floor_pass=0.28.
    # Three back-to-back runs over the 18-file corpus showed real small-model variance:
    #   run A: convergence=0.39 / citation=0.39 / floor=0.33
    #   run B: convergence=0.50 / citation=0.50 / floor=0.44
    #   run C: convergence=0.33 / citation=0.33 / floor=0.28  (lowest observed)
    # The floor is pinned AT the lowest observed run (0.33, floor-rounded-down) so the
    # gate is stable rather than flaky; Phase B (+#2/#3) must raise these numbers and
    # tighten the floor. The /md, /docx, /vtt, and /json cases were the consistent
    # non-converging cases across all three runs.
    assert card.convergence_rate >= 0.33
    assert card.citation_round_trip_rate >= 0.33
