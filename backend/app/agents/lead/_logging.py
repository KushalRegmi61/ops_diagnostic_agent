"""Shared structured logging helpers for lead-agent nodes."""
from app.llm.base import GenerateMetadata


def llm_meta_fields(meta: GenerateMetadata | None) -> dict:
    """Return compact LLM telemetry fields safe to emit in logs."""
    if meta is None:
        return {}
    return {
        "provider": meta.provider,
        "model": meta.model,
        "prompt_name": meta.prompt_name,
        "token_estimate": meta.token_estimate,
        "parsed_json": meta.parsed_json,
        "retry_count": meta.retry_count,
        "latency_ms": meta.latency_ms,
    }
