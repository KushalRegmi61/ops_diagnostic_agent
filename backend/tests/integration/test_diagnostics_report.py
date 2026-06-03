"""Skip-gated real-provider diagnostic report over the full corpus.

Measures, does not gate: asserts the report is well-formed and prints the per-file
funnel + structural probe + failure-stage so the diagnosis is captured in output.

Funnel-count caveat: the funnel is captured via the ``on_tool_call`` seam, which
replays the FINAL transcript once at run-end. The loop sawtooth-compacts every
``AGENT_COMPACT_EVERY`` (default 4) turns, so on a compacted run the funnel COUNTS
are tail-biased (reads/cites before the first compaction are dropped). The
failure-STAGE labels stay robust either way; only magnitudes drift. For faithful
counts, run with ``AGENT_COMPACT_EVERY=0``.
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


@pytest.mark.xfail(
    strict=False,
    reason=(
        "#2b soft steering lifts convergence 10/18 -> 13/18 but 2 non-JSON files "
        "(discovery_call.txt, leads_pipeline.csv) still cite-without-extract. The deeper "
        "fold-validation-into-extract fix is deferred to #2c; an XPASS here means #2c "
        "closed the gap and this marker should be removed."
    ),
)
def test_steering_lifts_non_json_behavioral_failures():
    """After #2b, previously-stalling non-JSON files commit at least one extract.

    Funnel gate: no non-JSON file may end in 'behavioral_steering' while having cited
    (cite_calls > 0) yet committed nothing (extract_calls == 0) — that is exactly the
    cite->extract stall #2b targets. JSON files are excluded (tiny-segments parser issue
    deferred to #2c). Convergence is reported for context, not hard-asserted (small-model
    variance).

    Marked xfail (non-strict): #2b's soft nudge fixed most stalls (+3 convergence) but two
    non-JSON files still cite-without-extract; the strict zero-offenders bar is met only
    once the #2c deeper fix lands.
    """
    get_provider.cache_clear()
    report = run_diagnostics(get_provider())

    converged = sum(1 for d in report.diagnostics if d.failure_stage == "converges")
    non_json = [d for d in report.diagnostics if d.type != "json"]
    offenders = [
        (d.file, d.funnel.cite_calls, d.funnel.extract_calls)
        for d in non_json
        if d.failure_stage == "behavioral_steering"
        and d.funnel.cite_calls > 0
        and d.funnel.extract_calls == 0
    ]

    print(f"\n[#2b] convergence={converged}/{len(report.diagnostics)} "
          f"non_json_cite_without_extract={len(offenders)}")

    assert not offenders, f"non-JSON files still cite without extracting: {offenders}"
