"""Skip-gated real-provider diagnostic report over the full corpus.

Measures, does not gate: asserts the report is well-formed and prints the per-file
funnel + structural probe + failure-stage so the diagnosis is captured in output.
"""
import pytest

from app.config import get_settings
from app.llm import get_provider
from evals.diagnostics import format_report, run_diagnostics
from evals.loader import load_cases

_VALID_STAGES = {"converges", "retrieval_or_parser", "cite_roundtrip_parser", "behavioral_steering"}


def _provider_up() -> bool:
    """True when the configured provider is constructible."""
    try:
        settings = get_settings()
        provider = get_provider()
        return provider is not None and bool(settings.llm_provider)
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _provider_up(), reason="LLM provider not reachable")


def test_diagnostics_report_is_complete_over_corpus():
    """Every corpus file yields a complete diagnostic; print the diagnosis table."""
    get_provider.cache_clear()
    report = run_diagnostics(get_provider())

    print("\nDIAGNOSTICS:\n" + format_report(report))

    assert len(report.diagnostics) == len(load_cases())
    for d in report.diagnostics:
        assert d.funnel.terminal_reason in {"model_finalize", "force_finalize", "fallback"}
        assert d.failure_stage in _VALID_STAGES
        assert d.probe.segment_count >= 0
