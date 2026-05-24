"""Lead node: review per-file summaries and optionally request a bounded redo.

Single-shot LLM call over the dict of FileSummary objects produced by the
per-file ReAct agents. Returns a SummaryReview whose ``revision_requests``
list, when non-empty, triggers the ``redo_inc`` branch in the parent graph
(capped at one pass).
"""
import json
import time

from app.agents.lead._logging import llm_meta_fields
from app.llm.base import LLMProvider
from app.prompts.review_summaries import PROMPT
from app.schemas import FileSummary, SummaryReview
from app.structured_logging import get_logger


logger = get_logger(__name__)


def run(*, provider: LLMProvider, file_summaries: dict[str, FileSummary]) -> SummaryReview:
    """Gate per-file summaries via one LLM call; degrades to a no-revision review on parse failure."""
    started = time.perf_counter()
    logger.info("agent.lead.started", agent="review_summaries", file_summary_count=len(file_summaries))
    summaries_json = json.dumps(
        {fid: fs.model_dump() for fid, fs in file_summaries.items()}, indent=2,
    )
    prompt = PROMPT.format(summaries_json=summaries_json)
    result, meta = provider.generate_json(
        prompt_name="review_summaries", prompt=prompt, schema=SummaryReview,
    )
    if not result:
        review = SummaryReview(revision_requests=[], notes="(reviewer failed to produce valid JSON — skipping redo)")
        logger.warning(
            "agent.lead.completed",
            agent="review_summaries",
            revision_request_count=0,
            fallback="skip_redo",
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            **llm_meta_fields(meta),
        )
        return review
    review = SummaryReview.model_validate(result)
    logger.info(
        "agent.lead.completed",
        agent="review_summaries",
        revision_request_count=len(review.revision_requests),
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        **llm_meta_fields(meta),
    )
    return review
