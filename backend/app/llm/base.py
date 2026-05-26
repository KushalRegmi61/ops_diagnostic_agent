"""LLM provider Protocol and the metadata record returned alongside each call.

Every provider implementation in this package conforms to ``LLMProvider`` so
the graph and ReAct tools can treat them uniformly. ``GenerateMetadata`` is
attached to observability spans and run records.
"""
from typing import Protocol, Type

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel


class GenerateMetadata(BaseModel):
    """Structured per-call telemetry: provider, model, token estimate, retries, latency."""

    provider: str
    model: str
    prompt_name: str
    token_estimate: int
    parsed_json: bool
    retry_count: int
    latency_ms: int


class LLMParseError(Exception):
    """Raised by lead/per-file agents when provider.generate_json returns parsed_json=False.

    Carries the structured stage/file_id/message that graph node wrappers convert
    into an ExtractionError appended to DiagnosticState['errors'].
    """

    def __init__(self, *, stage: str, message: str, file_id: str = "") -> None:
        super().__init__(f"{stage}: {message}")
        self.stage = stage
        self.message = message
        self.file_id = file_id


class LLMProvider(Protocol):
    """Protocol implemented by every concrete provider in ``app.llm``."""

    name: str
    model: str

    def chat_model(
        self,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        seed: int | None = None,
    ) -> BaseChatModel:
        """Return a LangChain chat model for agent/tool execution."""
        ...

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
        """Generate a JSON object validated against ``schema`` and return it with metadata."""
        ...
