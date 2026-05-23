"""GroqProvider.generate_json smoke test against the real Groq API.

Skipped unless GROQ_API_KEY is set in the environment.
"""
import os

import pytest
from pydantic import BaseModel

from app.llm.groq import GroqProvider

API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class EchoSchema(BaseModel):
    sentiment: str
    confidence: float


@pytest.mark.skipif(not API_KEY, reason="GROQ_API_KEY not set")
def test_groq_generate_json_returns_schema_valid_object():
    """Groq generate_json returns a schema-valid object with parsed_json=True."""
    provider = GroqProvider(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
    prompt = (
        "Classify the sentiment of: 'This product is great!'.\n"
        "Reply with JSON: {\"sentiment\": \"positive|negative|neutral\", \"confidence\": float in [0,1]}."
    )
    result, meta = provider.generate_json(prompt_name="sentiment", prompt=prompt, schema=EchoSchema)
    EchoSchema.model_validate(result)
    assert meta.provider == "groq"
    assert meta.parsed_json is True
