import json

from app.llm.base import LLMProvider
from app.prompts.synthesis import PROMPT
from app.schemas import FileSummary, IntakeBundle


def run(*, provider: LLMProvider, file_summaries: dict[str, FileSummary]) -> IntakeBundle:
    summaries_json = json.dumps(
        {fid: fs.model_dump() for fid, fs in file_summaries.items()}, indent=2,
    )
    prompt = PROMPT.format(summaries_json=summaries_json)
    result, _meta = provider.generate_json(
        prompt_name="cross_file_synthesis", prompt=prompt, schema=IntakeBundle,
    )
    if not result:
        return IntakeBundle(
            workflows=[], pain_signals=[], lead_rows=[],
            contradictions=[], file_index=[], extraction_errors=[],
        )
    return IntakeBundle.model_validate(result)
