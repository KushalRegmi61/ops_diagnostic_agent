"""Loader reads the manifest into typed cases and parses each via app.parsers."""
from evals.loader import CorpusCase, load_cases, parse_case
from app.schemas import ParsedFile


def test_load_cases_returns_typed_cases_for_every_family():
    cases = load_cases()
    assert len(cases) >= 10
    assert all(isinstance(c, CorpusCase) for c in cases)
    assert {"pdf", "csv", "json", "vtt", "mbox"} <= {c.type for c in cases}


def test_parse_case_round_trips_to_parsedfile():
    case = next(c for c in load_cases() if c.type == "md")
    parsed = parse_case(case)
    assert isinstance(parsed, ParsedFile)
    assert parsed.type == "md"
    assert len(parsed.segments) >= 1
