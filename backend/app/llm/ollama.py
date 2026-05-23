import json
import time
from typing import Type

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import GenerateMetadata


class OllamaProvider:
    name = "ollama"

    def __init__(self, *, base_url: str, model: str, timeout_s: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

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
        options: dict = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if top_p is not None:
            options["top_p"] = top_p
        if seed is not None:
            options["seed"] = seed

        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": options,
        }
        retry_count = 0
        start = time.perf_counter()

        for _ in range(2):
            with httpx.Client(timeout=self.timeout_s) as client:
                r = client.post(f"{self.base_url}/api/chat", json=body)
                r.raise_for_status()
                payload = r.json()
                content = payload.get("message", {}).get("content", "")

            try:
                parsed = json.loads(content)
                schema.model_validate(parsed)
                latency_ms = int((time.perf_counter() - start) * 1000)
                return parsed, GenerateMetadata(
                    provider=self.name,
                    model=self.model,
                    prompt_name=prompt_name,
                    token_estimate=len(prompt) // 4 + len(content) // 4,
                    parsed_json=True,
                    retry_count=retry_count,
                    latency_ms=latency_ms,
                )
            except (json.JSONDecodeError, ValidationError) as e:
                retry_count += 1
                body["messages"].append({
                    "role": "user",
                    "content": f"Your previous response failed to parse as the required JSON: {e}. Reply with ONLY valid JSON matching the schema.",
                })

        latency_ms = int((time.perf_counter() - start) * 1000)
        return {}, GenerateMetadata(
            provider=self.name,
            model=self.model,
            prompt_name=prompt_name,
            token_estimate=len(prompt) // 4,
            parsed_json=False,
            retry_count=retry_count,
            latency_ms=latency_ms,
        )
