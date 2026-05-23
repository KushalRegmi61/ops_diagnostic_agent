import json

from app.llm.base import LLMProvider
from app.prompts.review_summaries import PROMPT
from app.schemas import FileSummary, SummaryReview


def run(*, provider: LLMProvider, file_summaries: dict[str, FileSummary]) -> SummaryReview:
    summaries_json = json.dumps(
        {fid: fs.model_dump() for fid, fs in file_summaries.items()}, indent=2,
    )
    prompt = PROMPT.format(summaries_json=summaries_json)
    result, _meta = provider.generate_json(
        prompt_name="review_summaries", prompt=prompt, schema=SummaryReview,
    )
    if not result:
        return SummaryReview(revision_requests=[], notes="(reviewer failed to produce valid JSON — skipping redo)")
    return SummaryReview.model_validate(result)
