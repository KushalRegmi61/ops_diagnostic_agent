import json
import time
from typing import Type

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.llm.base import GenerateMetadata


class OpenAIProvider:
    name = "openai"

    def __init__(self, *, api_key: str, model: str, base_url: str | None = None) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self.model = model

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
    ) -> tuple[dict, GenerateMetadata]:
        retry_count = 0
        messages: list[dict] = [{"role": "user", "content": prompt}]
        start = time.perf_counter()

        extra_kwargs: dict = {}
        if max_tokens is not None:
            extra_kwargs["max_tokens"] = max_tokens
        if top_p is not None:
            extra_kwargs["top_p"] = top_p
        if seed is not None:
            extra_kwargs["seed"] = seed

        for _ in range(2):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
                **extra_kwargs,
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0

            try:
                parsed = json.loads(content)
                schema.model_validate(parsed)
                latency_ms = int((time.perf_counter() - start) * 1000)
                return parsed, GenerateMetadata(
                    provider=self.name,
                    model=self.model,
                    prompt_name=prompt_name,
                    token_estimate=tokens,
                    parsed_json=True,
                    retry_count=retry_count,
                    latency_ms=latency_ms,
                )
            except (json.JSONDecodeError, ValidationError) as e:
                retry_count += 1
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Previous reply did not match the schema: {e}. Return ONLY valid JSON."})

        latency_ms = int((time.perf_counter() - start) * 1000)
        return {}, GenerateMetadata(
            provider=self.name,
            model=self.model,
            prompt_name=prompt_name,
            token_estimate=0,
            parsed_json=False,
            retry_count=retry_count,
            latency_ms=latency_ms,
        )
