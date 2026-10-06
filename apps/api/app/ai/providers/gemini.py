from typing import Any

from google import genai
from google.genai import errors, types

from app.ai.providers.base import (
    AIProviderError,
    AIResponse,
    AIUsage,
    EmbeddingResponse,
    normalize_vector,
)

# Gemini rejects length/count constraints in larger response schemas ("invalid argument").
# They are still enforced: callers validate every response with the full Pydantic model.
_UNSUPPORTED_KEYWORDS = {"maxLength", "minLength", "maxItems", "minItems"}


def gemini_schema(schema: Any) -> Any:
    """Copy of a JSON schema without the keywords Gemini refuses."""
    if isinstance(schema, dict):
        result: dict[str, Any] = {}
        for key, value in schema.items():
            if key == "properties" and isinstance(value, dict):
                # Property names are data, not keywords; only recurse into their schemas.
                result[key] = {name: gemini_schema(sub) for name, sub in value.items()}
            elif key not in _UNSUPPORTED_KEYWORDS:
                result[key] = gemini_schema(value)
        return result
    if isinstance(schema, list):
        return [gemini_schema(item) for item in schema]
    return schema


class GeminiProvider:
    name = "gemini"

    def __init__(
        self, *, api_key: str, model: str, embedding_model: str, timeout_seconds: int
    ) -> None:
        self.model = model
        self.embedding_model = embedding_model
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=timeout_seconds * 1000)
        )

    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], max_output_tokens: int
    ) -> AIResponse:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_json_schema=gemini_schema(schema),
                    max_output_tokens=max_output_tokens,
                    temperature=0,
                    # Plain JSON generation; never let the SDK run tools on our behalf.
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
        except errors.APIError as exc:
            retryable = exc.code in (408, 429) or (exc.code or 0) >= 500
            raise AIProviderError(f"Gemini error {exc.code}", retryable=retryable) from exc
        except Exception as exc:  # network errors and timeouts from the HTTP client
            raise AIProviderError(
                f"Gemini request failed: {type(exc).__name__}", retryable=True
            ) from exc

        meta = response.usage_metadata
        usage = AIUsage(
            input_tokens=(meta.prompt_token_count or 0) if meta else 0,
            output_tokens=((meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0))
            if meta
            else 0,
        )
        if not response.text:
            raise AIProviderError("Gemini returned no content", retryable=True, usage=usage)
        return AIResponse(text=response.text, usage=usage)

    def embed(self, texts: list[str], *, dims: int) -> EmbeddingResponse:
        try:
            response = self._client.models.embed_content(
                model=self.embedding_model,
                # One Content per text: multimodal models would otherwise merge a list of
                # strings into a single multi-part input and return one vector.
                contents=[types.Content(parts=[types.Part(text=t)]) for t in texts],
                config=types.EmbedContentConfig(
                    output_dimensionality=dims, task_type="SEMANTIC_SIMILARITY"
                ),
            )
        except errors.APIError as exc:
            retryable = exc.code in (408, 429) or (exc.code or 0) >= 500
            raise AIProviderError(
                f"Gemini embedding error {exc.code}", retryable=retryable
            ) from exc
        except Exception as exc:
            raise AIProviderError(
                f"Gemini embedding failed: {type(exc).__name__}", retryable=True
            ) from exc
        vectors = [normalize_vector(list(e.values or [])) for e in response.embeddings or []]
        if len(vectors) != len(texts) or any(len(v) != dims for v in vectors):
            raise AIProviderError("Gemini returned unexpected embeddings", retryable=False)
        # The API does not report embedding tokens; estimate ~4 characters per token for budgeting.
        return EmbeddingResponse(vectors, AIUsage(sum(len(t) for t in texts) // 4, 0))
