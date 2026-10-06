"""Deterministic provider for tests. Replays queued responses and records every call."""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.providers.base import (
    AIProviderError,
    AIResponse,
    AIUsage,
    EmbeddingResponse,
    normalize_vector,
)


@dataclass
class FakeCall:
    system: str
    prompt: str
    schema: dict[str, Any]


@dataclass
class FakeAIProvider:
    responses: list[str | AIProviderError] = field(default_factory=list)
    name: str = "fake"
    model: str = "fake-model"
    embedding_model: str = "fake-embedding"
    calls: list[FakeCall] = field(default_factory=list)
    embed_calls: list[list[str]] = field(default_factory=list)

    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], max_output_tokens: int
    ) -> AIResponse:
        self.calls.append(FakeCall(system=system, prompt=prompt, schema=schema))
        if not self.responses:
            raise AssertionError("FakeAIProvider has no queued response")
        nxt = self.responses.pop(0)
        if isinstance(nxt, AIProviderError):
            raise nxt
        return AIResponse(
            text=nxt, usage=AIUsage(input_tokens=len(prompt) // 4, output_tokens=len(nxt) // 4)
        )

    def embed(self, texts: list[str], *, dims: int) -> EmbeddingResponse:
        """Deterministic bag-of-words vectors: texts sharing words are similar."""
        self.embed_calls.append(list(texts))
        vectors = []
        for text in texts:
            vec = [0.0] * dims
            for word in re.findall(r"[a-z0-9+#]+", text.lower()):
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % dims] += 1.0  # noqa: S324
            vectors.append(normalize_vector(vec))
        return EmbeddingResponse(vectors, AIUsage(sum(len(t) for t in texts) // 4, 0))
