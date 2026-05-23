"""Deterministic checks inside self_review_final (existence + reachability).

These do not invoke the LLM.
"""
from pathlib import Path

from app.agents.lead.self_review_final import _check_existence, _check_reachability, _all_sources
from app.parsers.md import parse as md_parse
from app.schemas import Blueprint, BlueprintClaim, Source


def _src(file_id: str = "f1", line_start: int = 1, line_end: int = 1) -> Source:
    return Source(
        file_id=file_id, file_name="x.md", type="md",
        locator={"type": "text", "line_start": line_start, "line_end": line_end},
    )


def _bp(sources: list[Source]) -> Blueprint:
    claim = BlueprintClaim(text="t", sources=sources)
    return Blueprint(
        opportunity_ref=0, summary=claim, steps=[claim],
        required_systems=[claim], success_metrics=[claim], risks=[claim],
    )


def test_existence_passes_when_all_ids_in_index():
    bp = _bp([_src("f1")])
    ok, bad = _check_existence(_all_sources(bp), {"f1"})
    assert ok and bad == []


def test_existence_fails_on_unknown_id():
    bp = _bp([_src("f1"), _src("f_ghost")])
    ok, bad = _check_existence(_all_sources(bp), {"f1"})
    assert not ok
    assert "f_ghost" in bad


def test_reachability_round_trips_through_parser(tmp_path: Path):
    p = tmp_path / "doc.md"
    p.write_text("# Hello\n\nSome body text.\n")
    parsed = md_parse(file_id="f1", file_name="doc.md", path=p)

    bp = _bp([_src("f1", line_start=1, line_end=1)])
    ok, bad = _check_reachability(_all_sources(bp), {"f1": parsed})
    assert ok, bad


def test_reachability_fails_on_missing_parsed_file():
    bp = _bp([_src("f_unknown")])
    ok, bad = _check_reachability(_all_sources(bp), {})
    assert not ok
    assert bad[0][0] == "f_unknown"


def test_reachability_fails_on_bad_locator(tmp_path: Path):
    p = tmp_path / "doc.md"
    p.write_text("# Hi\n")
    parsed = md_parse(file_id="f1", file_name="doc.md", path=p)
    # Out-of-range lines.
    bp = _bp([Source(file_id="f1", file_name="doc.md", type="md",
                     locator={"type": "text", "line_start": 999, "line_end": 1000})])
    ok, bad = _check_reachability(_all_sources(bp), {"f1": parsed})
    assert not ok
