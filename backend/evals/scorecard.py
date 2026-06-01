"""Score per-file agent output against expected floors and citation round-trip.

``score_summary`` is pure (no LLM, no provider) so it is fully unit-testable.
``run_scorecard`` drives the real agent over the corpus and aggregates metrics;
it is exercised only by the skip-gated integration gate.
"""
from pydantic import BaseModel

from app.agents.per_file._react_loop import run_react_loop
from app.parsers import excerpt
from app.schemas import FileSummary, ParsedFile
from evals.loader import CorpusCase, load_cases, parse_case

_PARTIAL_PREFIX = "(partial"


class FileScore(BaseModel):
    """Scored outcome for one corpus case."""

    file: str
    type: str
    converged: bool
    citations_round_trip: bool
    workflows: int
    pain_signals: int
    lead_rows: int
    citations: int
    meets_floor: bool


class Scorecard(BaseModel):
    """Aggregate metrics across the corpus."""

    convergence_rate: float
    citation_round_trip_rate: float
    floor_pass_rate: float
    avg_findings: float
    scores: list[FileScore]


def _all_sources(summary: FileSummary) -> list:
    """Flatten every Source across workflows, pain signals, and lead rows."""
    out = []
    for w in summary.key_workflows:
        out.extend(w.sources)
    for p in summary.key_pain_signals:
        out.extend(p.sources)
    for r in summary.lead_rows:
        out.append(r.source)
    return out


def score_summary(case: CorpusCase, summary: FileSummary, parsed: ParsedFile) -> FileScore:
    """Score one summary: convergence, citation round-trip, and floor compliance."""
    converged = not summary.one_paragraph_summary.startswith(_PARTIAL_PREFIX)
    sources = _all_sources(summary)
    citations = len(sources)
    round_trip = all(bool(excerpt(parsed, s.locator)) for s in sources) if sources else False

    meets_floor = (
        converged
        and len(summary.key_workflows) >= case.min_workflows
        and len(summary.key_pain_signals) >= case.min_pain_signals
        and len(summary.lead_rows) >= case.min_lead_rows
        and citations >= case.min_citations
        and (round_trip or case.min_citations == 0)
    )
    return FileScore(
        file=case.file, type=case.type, converged=converged,
        citations_round_trip=round_trip if sources else (case.min_citations == 0),
        workflows=len(summary.key_workflows), pain_signals=len(summary.key_pain_signals),
        lead_rows=len(summary.lead_rows), citations=citations, meets_floor=meets_floor,
    )


def run_scorecard(provider, cases: list[CorpusCase] | None = None, *, iteration_cap: int = 6) -> Scorecard:
    """Run the real per-file agent over the corpus and aggregate metrics."""
    cases = cases or load_cases()
    scores: list[FileScore] = []
    for case in cases:
        parsed = parse_case(case)
        summary = run_react_loop(provider=provider, parsed=parsed, iteration_cap=iteration_cap)
        scores.append(score_summary(case, summary, parsed))

    n = len(scores) or 1
    return Scorecard(
        convergence_rate=sum(s.converged for s in scores) / n,
        citation_round_trip_rate=sum(s.citations_round_trip for s in scores) / n,
        floor_pass_rate=sum(s.meets_floor for s in scores) / n,
        avg_findings=sum(s.workflows + s.pain_signals + s.lead_rows for s in scores) / n,
        scores=scores,
    )
