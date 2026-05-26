"""Shared LangChain-backed provider utilities."""
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Literal, Type

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ValidationError

from app.llm.base import GenerateMetadata
from app.observability import langchain_config

StructuredMethod = Literal["function_calling", "json_mode", "json_schema"]


class LangChainJSONProvider(ABC):
    """Base class for providers that generate schema-validated JSON via LangChain."""

    name: str
    model: str
    structured_method: StructuredMethod = "json_mode"
    strict_schema: bool | None = None

    @abstractmethod
    def chat_model(
        self,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        seed: int | None = None,
    ) -> BaseChatModel:
        """Return a configured LangChain chat model for this provider."""

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
        """Invoke a LangChain structured-output runnable and return parsed JSON plus metadata."""
        retry_count = 0
        prompt_text = self._prompt_for_method(prompt, schema)
        start = time.perf_counter()

        llm = self.chat_model(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            seed=seed,
        )
        structured_llm = llm.with_structured_output(
            schema,
            method=self.structured_method,
            include_raw=True,
            strict=self.strict_schema,
        )
        config = langchain_config(
            provider=self.name,
            model=self.model,
            prompt_name=prompt_name,
        )

        for _ in range(2):
            try:
                response = structured_llm.invoke(prompt_text, config=config)
                parsed = response.get("parsed") if isinstance(response, dict) else response
                if parsed is None:
                    raise ValueError(response.get("parsing_error") if isinstance(response, dict) else "no parsed output")
                result = parsed.model_dump() if isinstance(parsed, BaseModel) else parsed
                schema.model_validate(result)
                return result, GenerateMetadata(
                    provider=self.name,
                    model=self.model,
                    prompt_name=prompt_name,
                    token_estimate=token_count(response.get("raw") if isinstance(response, dict) else None),
                    parsed_json=True,
                    retry_count=retry_count,
                    latency_ms=int((time.perf_counter() - start) * 1000),
                )
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                retry_count += 1
                prompt_text = self._retry_prompt(prompt, schema, e)

        return {}, GenerateMetadata(
            provider=self.name,
            model=self.model,
            prompt_name=prompt_name,
            token_estimate=0,
            parsed_json=False,
            retry_count=retry_count,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    def _prompt_for_method(self, prompt: str, schema: Type[BaseModel]) -> str:
        if self.structured_method == "json_schema":
            return prompt
        return (
            f"{prompt}\n\nReturn ONLY valid JSON matching this JSON Schema:\n"
            f"{json.dumps(schema.model_json_schema())}"
        )

    def _retry_prompt(self, prompt: str, schema: Type[BaseModel], error: Exception) -> str:
        return (
            f"{prompt}\n\nPrevious reply did not match the required JSON schema: {error}.\n"
            f"Return ONLY valid JSON matching this JSON Schema:\n{json.dumps(schema.model_json_schema())}"
        )


def token_count(raw_message: object) -> int:
    """Extract total token usage from common LangChain AIMessage metadata shapes."""
    usage_metadata = getattr(raw_message, "usage_metadata", None) or {}
    total = usage_metadata.get("total_tokens")
    if isinstance(total, int):
        return total

    response_metadata = getattr(raw_message, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage") or {}
    total = token_usage.get("total_tokens")
    return total if isinstance(total, int) else 0


def metadata_from_message(raw_message: object) -> dict[str, Any]:
    """Return raw LangChain response metadata for diagnostics/tests."""
    return getattr(raw_message, "response_metadata", None) or {}
