from functools import lru_cache

from app.config import get_settings
from app.llm.base import GenerateMetadata, LLMProvider


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        from app.llm.ollama import OllamaProvider
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.ollama_model)
    if settings.llm_provider == "openai":
        from app.llm.openai import OpenAIProvider
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY required when LLM_PROVIDER=openai")
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)
    if settings.llm_provider == "groq":
        from app.llm.groq import GroqProvider
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY required when LLM_PROVIDER=groq")
        return GroqProvider(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            model=settings.groq_model,
        )
    if settings.llm_provider == "openai_compatible":
        from app.llm.openai_compat import OpenAICompatProvider
        if not (settings.openai_compatible_api_key and settings.openai_compatible_base_url and settings.openai_compatible_model):
            raise RuntimeError("OPENAI_COMPATIBLE_* env vars required when LLM_PROVIDER=openai_compatible")
        return OpenAICompatProvider(
            api_key=settings.openai_compatible_api_key,
            base_url=settings.openai_compatible_base_url,
            model=settings.openai_compatible_model,
        )
    raise RuntimeError(f"unknown LLM_PROVIDER={settings.llm_provider}")


__all__ = ["GenerateMetadata", "LLMProvider", "get_provider"]
