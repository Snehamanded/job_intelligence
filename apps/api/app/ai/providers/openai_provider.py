from typing import Any

import openai

from app.ai.providers.base import (
    AIProviderError,
    AIResponse,
    AIUsage,
    EmbeddingResponse,
    normalize_vector,
)


class OpenAIProvider:
    name = "openai"

    def __init__(
        self, *, api_key: str, model: str, embedding_model: str, timeout_seconds: int
    ) -> None:
        self.model = model
        self.embedding_model = embedding_model
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], max_output_tokens: int
    ) -> AIResponse:
        try:
            response = self._client.responses.create(
                model=self.model,
                instructions=system,
                input=prompt,
                max_output_tokens=max_output_tokens,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "extraction",
                        "schema": schema,
                        "strict": False,
                    }
                },
            )
        except (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError) as exc:
            raise AIProviderError(f"OpenAI {type(exc).__name__}", retryable=True) from exc
        except openai.APIStatusError as exc:
            raise AIProviderError(
                f"OpenAI error {exc.status_code}", retryable=exc.status_code >= 500
            ) from exc

        usage = AIUsage(
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
        )
        if not response.output_text:
            raise AIProviderError("OpenAI returned no content", retryable=True, usage=usage)
        return AIResponse(text=response.output_text, usage=usage)

    def embed(self, texts: list[str], *, dims: int) -> EmbeddingResponse:
        try:
            response = self._client.embeddings.create(
                model=self.embedding_model, input=texts, dimensions=dims
            )
        except (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError) as exc:
            raise AIProviderError(f"OpenAI {type(exc).__name__}", retryable=True) from exc
        except openai.APIStatusError as exc:
            raise AIProviderError(
                f"OpenAI embedding error {exc.status_code}", retryable=exc.status_code >= 500
            ) from exc
        vectors = [normalize_vector(list(d.embedding)) for d in response.data]
        return EmbeddingResponse(vectors, AIUsage(response.usage.prompt_tokens, 0))
