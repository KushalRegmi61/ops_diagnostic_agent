"""Lead node: merge the per-file FileSummary dict into a single IntakeBundle.

The IntakeBundle is the canonical cross-file representation consumed by the
downstream five-node diagnostic chain (workflows, pain signals, lead rows,
contradictions, file_index, extraction_errors).
"""
import json
import time

from app.agents.lead._logging import llm_meta_fields
from app.llm.base import LLMParseError, LLMProvider
from app.prompts import synthesis as synthesis_prompt
from app.schemas import FileSummary, IntakeBundle, RunContext
from app.structured_logging import get_logger


logger = get_logger(__name__)


def run(
    *,
    provider: LLMProvider,
    file_summaries: dict[str, FileSummary],
    run_context: RunContext | None = None,
) -> IntakeBundle:
    """Cross-file synthesis via one LLM call; returns an empty bundle on parse failure."""
    started = time.perf_counter()
    logger.info("agent.lead.started", agent="synthesis", file_summary_count=len(file_summaries))
    summaries_json = json.dumps(
        {fid: fs.model_dump() for fid, fs in file_summaries.items()}, indent=2,
    )
    prompt = synthesis_prompt.render(run_context=run_context, summaries_json=summaries_json)
    result, meta = provider.generate_json(
        prompt_name="cross_file_synthesis", prompt=prompt, schema=IntakeBundle,
    )
    if not meta.parsed_json:
        raise LLMParseError(
            stage="synthesis",
            message=f"provider returned parsed_json=False after {meta.retry_count} retries",
        )
    bundle = IntakeBundle.model_validate(result)
    logger.info(
        "agent.lead.completed",
        agent="synthesis",
        workflow_count=len(bundle.workflows),
        pain_signal_count=len(bundle.pain_signals),
        lead_row_count=len(bundle.lead_rows),
        contradiction_count=len(bundle.contradictions),
        extraction_error_count=len(bundle.extraction_errors),
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        **llm_meta_fields(meta),
    )
    return bundle
