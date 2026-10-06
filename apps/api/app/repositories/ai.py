import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AIExtraction, LLMUsage


class LLMUsageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def tokens_this_month(self, user_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total = self._session.scalar(
            select(
                func.coalesce(func.sum(LLMUsage.input_tokens + LLMUsage.output_tokens), 0)
            ).where(LLMUsage.user_id == user_id, LLMUsage.created_at >= month_start)
        )
        return int(total or 0)

    def add(self, usage: LLMUsage) -> None:
        self._session.add(usage)
        self._session.flush()


class AIExtractionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self, user_id: uuid.UUID, task: str, content_hash: str, prompt_version: str, model: str
    ) -> AIExtraction | None:
        return self._session.scalar(
            select(AIExtraction).where(
                AIExtraction.user_id == user_id,
                AIExtraction.task == task,
                AIExtraction.content_hash == content_hash,
                AIExtraction.prompt_version == prompt_version,
                AIExtraction.model == model,
            )
        )

    def add(
        self,
        user_id: uuid.UUID,
        task: str,
        content_hash: str,
        prompt_version: str,
        model: str,
        output: dict[str, Any],
    ) -> None:
        self._session.add(
            AIExtraction(
                user_id=user_id,
                task=task,
                content_hash=content_hash,
                prompt_version=prompt_version,
                model=model,
                output=output,
            )
        )
        self._session.flush()
