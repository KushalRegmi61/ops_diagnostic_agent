"""Self-review of the final Blueprint.

Two deterministic checks + one LLM judgment:
  - citation_existence_ok: every Source.file_id appears in bundle.file_index.
  - citation_reachability_ok: every Source.locator round-trips through the parser's
    excerpt() and returns non-empty text.
  - no_silent_drops_ok + internal_consistency_ok: single-shot LLM judgment.
"""
import json
import time

from pydantic import BaseModel

from app.agents.lead._logging import llm_meta_fields
from app.llm.base import LLMProvider
from app.parsers import excerpt as parser_excerpt
from app.prompts.self_review_final import PROMPT
from app.schemas import (
    Blueprint,
    FileSummary,
    FinalReview,
    IntakeBundle,
    Opportunity,
    ParsedFile,
    Source,
)
from app.structured_logging import get_logger


logger = get_logger(__name__)


class _Judgment(BaseModel):
    """LLM-only portion of the final review (deterministic checks happen in code)."""
    no_silent_drops_ok: bool
    internal_consistency_ok: bool
    detail: str


def _all_sources(bp: Blueprint) -> list[Source]:
    """Flatten every Source across the Blueprint's summary, steps, systems, metrics, and risks."""
    out: list[Source] = []
    for claim in [bp.summary, *bp.steps, *bp.required_systems, *bp.success_metrics, *bp.risks]:
        out.extend(claim.sources)
    return out


def _check_existence(sources: list[Source], file_index_ids: set[str]) -> tuple[bool, list[str]]:
    """Verify every Source.file_id is known to the IntakeBundle.file_index; return (ok, bad_ids)."""
    bad = [s.file_id for s in sources if s.file_id not in file_index_ids]
    return (not bad), bad


def _check_reachability(
    sources: list[Source], parsed_files: dict[str, ParsedFile]
) -> tuple[bool, list[tuple[str, str]]]:
    """Round-trip each Source.locator through parser.excerpt; return (ok, list of (file_id, reason))."""
    bad: list[tuple[str, str]] = []
    for s in sources:
        parsed = parsed_files.get(s.file_id)
        if parsed is None:
            bad.append((s.file_id, "no parsed file in state"))
            continue
        try:
            text = parser_excerpt(parsed, s.locator)
            if not text or not text.strip():
                bad.append((s.file_id, "empty excerpt"))
        except (KeyError, ValueError, IndexError) as e:
            bad.append((s.file_id, str(e)))
    return (not bad), bad


def run(
    *,
    provider: LLMProvider,
    blueprint: Blueprint,
    bundle: IntakeBundle,
    selected: Opportunity,
    opportunities: list[Opportunity],
    file_summaries: dict[str, FileSummary],
    parsed_files: dict[str, ParsedFile],
    revised_once: bool,
) -> FinalReview:
    """Run deterministic citation checks and an LLM judgment; merged detail drives the revise_inc branch."""
    started = time.perf_counter()
    logger.info(
        "agent.lead.started",
        agent="self_review_final",
        revised_once=revised_once,
        opportunity_count=len(opportunities),
        file_summary_count=len(file_summaries),
    )
    file_index_ids = {s.file_id for s in bundle.file_index}
    sources = _all_sources(blueprint)
    logger.info("agent.lead.self_review.sources_collected", source_count=len(sources))

    existence_ok, bad_exist = _check_existence(sources, file_index_ids)
    reach_ok, bad_reach = _check_reachability(sources, parsed_files)
    logger.info(
        "agent.lead.self_review.deterministic_checks_completed",
        citation_existence_ok=existence_ok,
        citation_reachability_ok=reach_ok,
        bad_existence_count=len(bad_exist),
        bad_reachability_count=len(bad_reach),
    )

    open_questions = sorted({q for fs in file_summaries.values() for q in fs.open_questions})

    prompt = PROMPT.format(
        blueprint_json=json.dumps(blueprint.model_dump(), indent=2),
        selected_json=json.dumps(selected.model_dump(), indent=2),
        opportunities_json=json.dumps([o.model_dump() for o in opportunities], indent=2),
        open_questions_json=json.dumps(open_questions, indent=2),
    )
    result, meta = provider.generate_json(prompt_name="self_review_final", prompt=prompt, schema=_Judgment)
    if result:
        judgment = _Judgment.model_validate(result)
        fallback = None
    else:
        judgment = _Judgment(
            no_silent_drops_ok=True,
            internal_consistency_ok=True,
            detail="LLM judgment unavailable; deterministic checks only",
        )
        fallback = "deterministic_checks_only"

    detail_parts: list[str] = [judgment.detail]
    if bad_exist:
        detail_parts.append(f"unknown file_ids: {bad_exist}")
    if bad_reach:
        detail_parts.append(f"unreachable: {bad_reach}")

    review = FinalReview(
        citation_existence_ok=existence_ok,
        citation_reachability_ok=reach_ok,
        no_silent_drops_ok=judgment.no_silent_drops_ok,
        internal_consistency_ok=judgment.internal_consistency_ok,
        detail=" | ".join(p for p in detail_parts if p),
        revised_once=revised_once,
    )
    logger.info(
        "agent.lead.completed",
        agent="self_review_final",
        citation_existence_ok=review.citation_existence_ok,
        citation_reachability_ok=review.citation_reachability_ok,
        no_silent_drops_ok=review.no_silent_drops_ok,
        internal_consistency_ok=review.internal_consistency_ok,
        fallback=fallback,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        **llm_meta_fields(meta),
    )
    return review
