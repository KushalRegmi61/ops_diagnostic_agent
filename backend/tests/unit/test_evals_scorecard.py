"""Pure scoring: a FileSummary + case + parsed yields a deterministic FileScore."""
from evals.loader import CorpusCase, parse_case
from evals.scorecard import FileScore, score_summary
from app.schemas import FileSummary, PainSignal, Source


def _md_case() -> CorpusCase:
    return CorpusCase(file="producer_notes.md", type="md", min_pain_signals=1, min_citations=1)


def _summary_with_pain(parsed) -> FileSummary:
    # Build the Source from a real parsed segment so its locator round-trips via excerpt().
    seg = parsed.segments[0]
    src = Source(file_id=parsed.file_id, file_name=parsed.file_name, type=parsed.type, locator=seg.locator)
    return FileSummary(
        file_id=parsed.file_id, file_name=parsed.file_name,
        one_paragraph_summary="Real summary of producer pain points.",
        key_workflows=[],
        key_pain_signals=[PainSignal(text="Leads wait > 24h.", category="delay", sources=[src])],
        lead_rows=[], open_questions=[], agent_notes="",
    )


def test_score_summary_passes_when_floor_met_and_citation_round_trips():
    case = _md_case()
    parsed = parse_case(case)
    score = score_summary(case, _summary_with_pain(parsed), parsed)
    assert isinstance(score, FileScore)
    assert score.converged is True
    assert score.citations_round_trip is True
    assert score.meets_floor is True


def test_score_summary_flags_partial_summary_as_not_converged():
    case = _md_case()
    parsed = parse_case(case)
    partial = FileSummary(
        file_id=parsed.file_id, file_name=parsed.file_name,
        one_paragraph_summary="(partial — iteration cap reached)",
        key_workflows=[], key_pain_signals=[], lead_rows=[], open_questions=[], agent_notes="",
    )
    score = score_summary(case, partial, parsed)
    assert score.converged is False
    assert score.meets_floor is False
