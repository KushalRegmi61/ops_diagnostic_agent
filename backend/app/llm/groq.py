from app.llm.openai import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """Groq provider using ChatOpenAI against Groq's OpenAI-compatible endpoint."""

    name = "groq"
    structured_method = "json_mode"
    strict_schema = None

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url)
