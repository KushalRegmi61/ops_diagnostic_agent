import os

import pytest
from pydantic import BaseModel

from app.llm.openai import OpenAIProvider

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


class EchoSchema(BaseModel):
    sentiment: str
    confidence: float


@pytest.mark.skipif(not API_KEY, reason="OPENAI_API_KEY not set")
def test_openai_generate_json_returns_schema_valid_object():
    provider = OpenAIProvider(api_key=API_KEY, model=MODEL)
    prompt = (
        "Classify the sentiment of: 'This product is great!'.\n"
        "Respond with JSON: {\"sentiment\": \"positive|negative|neutral\", \"confidence\": float in [0,1]}."
    )
    result, meta = provider.generate_json(prompt_name="sentiment", prompt=prompt, schema=EchoSchema)
    EchoSchema.model_validate(result)
    assert meta.provider == "openai"
    assert meta.parsed_json is True
