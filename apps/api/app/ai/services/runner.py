"""Shared LLM call path: consent, cache, hard budget, retries, validation and usage records.

Never raises for LLM problems. Callers get a value, or None plus a user-facing notice, and fall
back to their non-AI path.
"""

import logging
import time
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai.providers import AIProvider, AIProviderError, AIUsage
from app.core.config import Settings
from app.models import LLMUsage
from app.repositories.ai import AIExtractionRepository, LLMUsageRepository

logger = logging.getLogger(__name__)

NOTICE_NO_CONSENT = "AI processing is off. Turn it on in Settings for better results."
NOTICE_NOT_CONFIGURED = "AI is not configured on this server."
NOTICE_BUDGET = "You have reached this month's AI usage limit."
NOTICE_FAILED = "The AI request failed. You can try again later."

MAX_ATTEMPTS = 2


@dataclass(frozen=True)
class LLMTask:
    name: str
    prompt_version: str
    system: str
    max_output_tokens: int


@dataclass(frozen=True)
class RunOutcome[T: BaseModel]:
    value: T | None
    notice: str | None
    from_cache: bool = False


class LLMRunner:
    def __init__(self, session: Session, provider: AIProvider | None, settings: Settings) -> None:
        self._session = session
        self._provider = provider
        self._settings = settings
        self._usage = LLMUsageRepository(session)
        self._cache = AIExtractionRepository(session)

    @property
    def available(self) -> bool:
        return self._provider is not None

    def record(
        self, user_id: uuid.UUID, task: str, usage: AIUsage | None, *, success: bool
    ) -> None:
        if self._provider is None:
            return
        self._usage.add(
            LLMUsage(
                user_id=user_id,
                task=task,
                provider=self._provider.name,
                model=self._provider.model,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                success=success,
            )
        )

    def within_budget(self, user_id: uuid.UUID, estimated_tokens: int) -> bool:
        used = self._usage.tokens_this_month(user_id)
        if used + estimated_tokens > self._settings.llm_monthly_token_budget:
            logger.warning("llm_budget_exceeded", extra={"user_id": str(user_id), "used": used})
            return False
        return True

    def run[T: BaseModel](
        self,
        user_id: uuid.UUID,
        task: LLMTask,
        *,
        prompt: str,
        schema: type[T],
        cache_key: str,
        consent: bool,
    ) -> RunOutcome[T]:
        if not consent:
            return RunOutcome(None, NOTICE_NO_CONSENT)
        provider = self._provider
        if provider is None:
            return RunOutcome(None, NOTICE_NOT_CONFIGURED)

        cached = self._cache.get(user_id, task.name, cache_key, task.prompt_version, provider.model)
        if cached is not None:
            try:
                return RunOutcome(schema.model_validate(cached.output), None, from_cache=True)
            except ValidationError:
                logger.warning("ai_cache_entry_invalid", extra={"task": task.name})

        # Conservative pre-call estimate (~4 characters per token) for the hard cap.
        estimate = (len(task.system) + len(prompt)) // 4 + task.max_output_tokens
        if not self.within_budget(user_id, estimate):
            return RunOutcome(None, NOTICE_BUDGET)

        json_schema = schema.model_json_schema()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = time.perf_counter()
            try:
                response = provider.generate_json(
                    system=task.system,
                    prompt=prompt,
                    schema=json_schema,
                    max_output_tokens=task.max_output_tokens,
                )
            except AIProviderError as exc:
                self.record(user_id, task.name, exc.usage, success=False)
                logger.warning(
                    "llm_call_failed",
                    extra={"task": task.name, "provider": provider.name, "attempt": attempt,
                           "error": str(exc), "retryable": exc.retryable},
                )  # fmt: skip
                if not exc.retryable or attempt == MAX_ATTEMPTS:
                    break
                time.sleep(self._settings.llm_retry_backoff_seconds * attempt)
                continue

            try:
                value = schema.model_validate_json(response.text)
            except ValidationError as exc:
                self.record(user_id, task.name, response.usage, success=False)
                logger.warning(
                    "llm_output_invalid",
                    extra={"task": task.name, "attempt": attempt, "errors": exc.error_count()},
                )
                continue

            self.record(user_id, task.name, response.usage, success=True)
            self._cache.add(
                user_id,
                task.name,
                cache_key,
                task.prompt_version,
                provider.model,
                value.model_dump(mode="json"),
            )
            logger.info(
                "llm_call_completed",
                extra={"task": task.name, "provider": provider.name, "model": provider.model,
                       "input_tokens": response.usage.input_tokens,
                       "output_tokens": response.usage.output_tokens,
                       "duration_ms": round((time.perf_counter() - started) * 1000)},
            )  # fmt: skip
            return RunOutcome(value, None)
        return RunOutcome(None, NOTICE_FAILED)
