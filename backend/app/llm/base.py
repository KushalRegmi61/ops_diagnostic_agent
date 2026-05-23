from typing import Protocol, Type

from pydantic import BaseModel


class GenerateMetadata(BaseModel):
    provider: str
    model: str
    prompt_name: str
    token_estimate: int
    parsed_json: bool
    retry_count: int
    latency_ms: int


class LLMProvider(Protocol):
    name: str

    def generate_json(
        self,
        *,
        prompt_name: str,
        prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        seed: int | None = None,
    ) -> tuple[dict, GenerateMetadata]: ...
