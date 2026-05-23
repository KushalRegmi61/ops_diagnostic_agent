"""GenerateMetadata dataclass field checks for the LLM provider Protocol."""
from app.llm.base import GenerateMetadata


def test_generate_metadata_fields():
    """GenerateMetadata stores provider/model/prompt diagnostics verbatim."""
    m = GenerateMetadata(
        provider="ollama",
        model="llama3.1:8b",
        prompt_name="echo",
        token_estimate=10,
        parsed_json=True,
        retry_count=0,
        latency_ms=120,
    )
    assert m.provider == "ollama"
    assert m.parsed_json is True
