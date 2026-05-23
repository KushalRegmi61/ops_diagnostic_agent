import httpx
import pytest
from pydantic import BaseModel

from app.config import get_settings
from app.llm.ollama import OllamaProvider


def _ollama_up(base_url: str) -> bool:
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


_settings = get_settings()
BASE_URL = _settings.ollama_base_url
MODEL = _settings.ollama_model


class EchoSchema(BaseModel):
    sentiment: str
    confidence: float


@pytest.mark.skipif(not _ollama_up(BASE_URL), reason="Ollama not reachable")
def test_ollama_generate_json_returns_schema_valid_object():
    provider = OllamaProvider(base_url=BASE_URL, model=MODEL)
    prompt = (
        "Classify the sentiment of: 'This product is great!'.\n"
        "Respond with JSON of the form {\"sentiment\": \"positive|negative|neutral\", \"confidence\": float between 0 and 1}."
    )
    result, meta = provider.generate_json(
        prompt_name="sentiment_classifier",
        prompt=prompt,
        schema=EchoSchema,
    )
    EchoSchema.model_validate(result)
    assert meta.provider == "ollama"
    assert meta.model == MODEL
    assert meta.prompt_name == "sentiment_classifier"
    assert meta.parsed_json is True
    assert meta.latency_ms > 0


@pytest.mark.skipif(not _ollama_up(BASE_URL), reason="Ollama not reachable")
def test_ollama_respects_sampling_params():
    """Sampling params (temperature, top_p, seed, max_tokens) must reach the wire and not crash."""
    provider = OllamaProvider(base_url=BASE_URL, model=MODEL)
    prompt = (
        "Pick a number between 1 and 10.\n"
        "Respond with JSON: {\"number\": <int>}."
    )

    class NumberSchema(BaseModel):
        number: int

    result, meta = provider.generate_json(
        prompt_name="number_pick",
        prompt=prompt,
        schema=NumberSchema,
        temperature=0.5,
        max_tokens=50,
        top_p=0.9,
        seed=42,
    )
    NumberSchema.model_validate(result)
    assert meta.parsed_json is True
