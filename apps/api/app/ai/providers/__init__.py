from app.ai.providers.base import AIProvider, AIProviderError, AIResponse, AIUsage
from app.core.config import Settings


def get_ai_provider(settings: Settings) -> AIProvider | None:
    """The configured provider, or None if AI is disabled or has no key."""
    if settings.ai_provider == "gemini" and settings.gemini_api_key:
        from app.ai.providers.gemini import GeminiProvider

        return GeminiProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            embedding_model=settings.gemini_embedding_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.ai_provider == "openai" and settings.openai_api_key:
        from app.ai.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
            embedding_model=settings.openai_embedding_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return None


__all__ = ["AIProvider", "AIProviderError", "AIResponse", "AIUsage", "get_ai_provider"]
