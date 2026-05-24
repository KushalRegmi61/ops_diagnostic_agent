"""Application configuration via pydantic-settings.

Reads `.env` into a `Settings` model that every layer (HTTP, services, graph,
agents, parsers, providers) consults through the cached `get_settings()`
accessor. Tests that mutate environment variables mid-suite must call
`get_settings.cache_clear()` to re-read.
"""
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    database_url: str
    blob_store_dir: str
    frontend_cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    llm_provider: Literal["ollama", "openai", "groq", "openai_compatible"] = "ollama"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    openai_compatible_api_key: str | None = None
    openai_compatible_base_url: str | None = None
    openai_compatible_model: str | None = None

    # Redis + LangGraph checkpointer
    redis_url: str = "redis://localhost:6379/0"
    langgraph_checkpointer: Literal["redis"] = "redis"
    langgraph_checkpoint_namespace: str = "ops_diagnostic"
    # TTL for LangGraph checkpoint keys in Redis, in minutes. None disables expiry
    # (keys persist until manually deleted). Default 1440 = 24h, enough to debug a
    # failed run the next morning while preventing unbounded growth.
    langgraph_checkpoint_ttl_minutes: int | None = 1440
    # If True, reading a checkpoint refreshes its TTL — useful for long-running
    # human-in-the-loop flows that should stay alive while a human is engaged.
    langgraph_checkpoint_refresh_on_read: bool = False

    # Langfuse
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://us.cloud.langfuse.com"

    # Run-time behavior
    auto_approve_review: bool = False
    per_file_iteration_cap: int = 6
    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"

    @field_validator("frontend_cors_origins", mode="before")
    @classmethod
    def _parse_frontend_cors_origins(cls, value: object) -> object:
        """Accept JSON-style lists or comma-separated env values for frontend origins."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


def get_settings() -> Settings:
    """Return a fresh Settings instance — call sites typically cache this themselves."""
    return Settings()
