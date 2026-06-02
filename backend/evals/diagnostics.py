"""Aggregate the per-file funnel + structural probe into a failure diagnosis.

Drives the real per-file agent over the corpus (mirroring run_scorecard), captures
the extraction funnel through the existing on_tool_call seam, runs the offline
structural probe, and classifies each file's failure stage. Output is a typed
report plus a human-readable table — no DB, no API, no production code change.
"""
from pydantic import BaseModel

from app.agents.per_file._react_loop import run_react_loop
from evals.funnel import RunFunnel, FunnelCollector, failure_stage, terminal_reason
from evals.loader import CorpusCase, load_cases, parse_case
from evals.structural import StructuralProbe, probe_structure


class FileDiagnostic(BaseModel):
    """Funnel + structural probe + classified stage for one corpus file."""

    file: str
    type: str
    funnel: RunFunnel
    probe: StructuralProbe
    failure_stage: str


class DiagnosticsReport(BaseModel):
    """All per-file diagnostics for one corpus run."""

    diagnostics: list[FileDiagnostic]


def run_diagnostics(provider, cases: list[CorpusCase] | None = None, *, iteration_cap: int = 6) -> DiagnosticsReport:
    """Run the corpus through the agent, capturing funnel + probe per file."""
    cases = cases or load_cases()
    out: list[FileDiagnostic] = []
    for case in cases:
        parsed = parse_case(case)
        probe = probe_structure(parsed)
        collector = FunnelCollector()
        summary = run_react_loop(
            provider=provider, parsed=parsed, iteration_cap=iteration_cap, on_tool_call=collector,
        )
        collector.funnel.terminal_reason = terminal_reason(summary)
        out.append(
            FileDiagnostic(
                file=case.file,
                type=case.type,
                funnel=collector.funnel,
                probe=probe,
                failure_stage=failure_stage(collector.funnel),
            )
        )
    return DiagnosticsReport(diagnostics=out)


def format_report(report: DiagnosticsReport) -> str:
    """Render the diagnostics as a fixed-width table for human reading."""
    header = (
        f"{'file':<22} {'type':<6} {'term':<14} {'srch':>4} {'hits':>4} "
        f"{'cite':>4} {'rt':>3} {'xtr':>3} {'segs':>4} {'flags':<24} stage"
    )
    lines = [header, "-" * len(header)]
    for d in report.diagnostics:
        f = d.funnel
        lines.append(
            f"{d.file:<22} {d.type:<6} {f.terminal_reason:<14} {f.searches_issued:>4} "
            f"{f.search_hits_returned:>4} {f.cite_calls:>4} {f.cite_round_trips:>3} "
            f"{f.extract_calls:>3} {d.probe.segment_count:>4} "
            f"{','.join(d.probe.flags):<24} {d.failure_stage}"
        )
    return "\n".join(lines)
