import hashlib
import logging
import time
import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers import AIProvider, AIProviderError
from app.ai.services.runner import LLMRunner
from app.core.config import Settings
from app.models import Embedding

logger = logging.getLogger(__name__)

BATCH = 20
TASK = "embedding"
# Free API tiers rate-limit embeddings per minute; wait and retry before giving up.
RETRY_DELAYS_SECONDS = (5, 15)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def cosine(a: list[float], b: list[float]) -> float:
    """Vectors are stored unit-length, so the dot product is the cosine similarity."""
    return sum(x * y for x, y in zip(a, b, strict=True))


class EmbeddingService:
    """Embeddings with a per-user cache keyed by content hash and model."""

    def __init__(
        self,
        session: Session,
        provider: AIProvider | None,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sleep = sleep
        self._session = session
        self._provider = provider
        self._settings = settings
        self._runner = LLMRunner(session, provider, settings)

    def get_many(
        self, user_id: uuid.UUID, texts: list[str], kind: str
    ) -> list[list[float] | None] | None:
        """Vectors per text (None where unavailable this run), or None if embeddings are off.

        Cached vectors are always returned. New ones are created batch by batch; if the provider
        refuses (quota), the rest stay None and are filled in on a later run.
        """
        provider = self._provider
        if provider is None or not texts:
            return None
        model = provider.embedding_model
        hashes = [content_hash(t) for t in texts]
        found: dict[str, list[float]] = {
            e.content_hash: list(e.vector)
            for e in self._session.scalars(
                select(Embedding).where(
                    Embedding.user_id == user_id,
                    Embedding.model == model,
                    Embedding.content_hash.in_(set(hashes)),
                )
            )
        }
        missing = list(dict.fromkeys(h for h in hashes if h not in found))
        text_by_hash = dict(zip(hashes, texts, strict=True))
        if missing and self._runner.within_budget(
            user_id, sum(len(text_by_hash[h]) for h in missing) // 4
        ):
            created = 0
            for i in range(0, len(missing), BATCH):
                batch = missing[i : i + BATCH]
                vectors = self._embed_with_retry(
                    user_id, provider, [text_by_hash[h] for h in batch]
                )
                if vectors is None:
                    break
                for h, vector in zip(batch, vectors, strict=True):
                    self._session.add(
                        Embedding(
                            user_id=user_id, kind=kind, content_hash=h, model=model, vector=vector
                        )
                    )
                    found[h] = vector
                created += len(batch)
            self._session.flush()
            logger.info(
                "embeddings_created",
                extra={"count": created, "kind": kind, "deferred": len(missing) - created},
            )
        return [found.get(h) for h in hashes]

    def _embed_with_retry(
        self, user_id: uuid.UUID, provider: AIProvider, texts: list[str]
    ) -> list[list[float]] | None:
        delays = [d * self._settings.llm_retry_backoff_seconds / 2 for d in RETRY_DELAYS_SECONDS]
        for attempt in range(len(delays) + 1):
            try:
                response = provider.embed(texts, dims=self._settings.embedding_dims)
            except AIProviderError as exc:
                self._runner.record(user_id, TASK, exc.usage, success=False)
                logger.warning(
                    "embedding_failed", extra={"error": str(exc), "attempt": attempt + 1}
                )
                if not exc.retryable or attempt == len(delays):
                    return None
                self._sleep(delays[attempt])
                continue
            self._runner.record(user_id, TASK, response.usage, success=True)
            return response.vectors
        return None
