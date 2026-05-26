"""When generate_json returns parsed_json=False, lead agents must raise LLMParseError."""
import pytest

from app.agents.lead import synthesis
from app.llm.base import GenerateMetadata, LLMParseError


class _FailingProvider:
    """Always returns ({}, parsed_json=False) — simulates total schema-mismatch failure."""
    name = "failing"
    model = "failing"

    def generate_json(self, *, prompt_name, prompt, schema, **kwargs):
        meta = GenerateMetadata(
            provider=self.name, model=self.model, prompt_name=prompt_name,
            token_estimate=0, parsed_json=False, retry_count=2, latency_ms=10,
        )
        return {}, meta

    def chat_model(self, **kwargs):
        raise NotImplementedError


def test_synthesis_raises_on_parsed_json_false() -> None:
    with pytest.raises(LLMParseError) as excinfo:
        synthesis.run(provider=_FailingProvider(), file_summaries={})
    assert excinfo.value.stage == "synthesis"
    assert "parse" in excinfo.value.message.lower() or "schema" in excinfo.value.message.lower() or "parsed_json" in excinfo.value.message.lower()
