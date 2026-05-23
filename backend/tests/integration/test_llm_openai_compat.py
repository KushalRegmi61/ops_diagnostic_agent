import os

import pytest
from pydantic import BaseModel

from app.llm.openai_compat import OpenAICompatProvider

API_KEY = os.getenv("OPENAI_COMPATIBLE_API_KEY")
BASE_URL = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
MODEL = os.getenv("OPENAI_COMPATIBLE_MODEL")


class EchoSchema(BaseModel):
    sentiment: str
    confidence: float


@pytest.mark.skipif(
    not (API_KEY and BASE_URL and MODEL),
    reason="OPENAI_COMPATIBLE_* env vars not all set",
)
def test_openai_compat_generate_json_returns_schema_valid_object():
    provider = OpenAICompatProvider(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
    prompt = "Reply with JSON: {\"sentiment\": \"positive\", \"confidence\": 0.9}."
    result, meta = provider.generate_json(prompt_name="echo", prompt=prompt, schema=EchoSchema)
    EchoSchema.model_validate(result)
    assert meta.provider == "openai_compatible"
