from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AIUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class AIResponse:
    text: str
    usage: AIUsage


@dataclass(frozen=True)
class EmbeddingResponse:
    vectors: list[list[float]]
    usage: AIUsage


class AIProviderError(Exception):
    """A provider call failed. `retryable` is True for timeouts, rate limits and 5xx."""

    def __init__(self, message: str, *, retryable: bool, usage: AIUsage | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.usage = usage


class AIProvider(Protocol):
    name: str
    model: str
    embedding_model: str

    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], max_output_tokens: int
    ) -> AIResponse:
        """Return raw JSON text. Callers validate it; providers never interpret it."""
        ...

    def embed(self, texts: list[str], *, dims: int) -> EmbeddingResponse:
        """Unit-length vectors of exactly `dims` dimensions, one per text."""
        ...


def normalize_vector(values: list[float]) -> list[float]:
    norm = sum(v * v for v in values) ** 0.5
    return [v / norm for v in values] if norm else values
