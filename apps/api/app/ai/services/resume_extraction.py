import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.prompts import resume_extraction as prompt
from app.ai.providers import AIProvider
from app.ai.schemas import ResumeExtraction
from app.ai.services import runner
from app.ai.services.runner import LLMRunner, LLMTask
from app.core.config import Settings

NOTICE_NO_CONSENT = (
    "AI parsing is off, so basic parsing was used. Turn on AI processing in Settings for "
    "better results."
)
NOTICE_NOT_CONFIGURED = "AI parsing is not configured on this server, so basic parsing was used."
NOTICE_BUDGET = "You have reached this month's AI usage limit, so basic parsing was used."
NOTICE_FAILED = "AI parsing failed, so basic parsing was used. You can try parsing again later."

# Resume-specific wording for the runner's generic notices.
_NOTICES = {
    runner.NOTICE_NO_CONSENT: NOTICE_NO_CONSENT,
    runner.NOTICE_NOT_CONFIGURED: NOTICE_NOT_CONFIGURED,
    runner.NOTICE_BUDGET: NOTICE_BUDGET,
    runner.NOTICE_FAILED: NOTICE_FAILED,
}

TASK = LLMTask(
    name=prompt.TASK,
    prompt_version=prompt.PROMPT_VERSION,
    system=prompt.SYSTEM_PROMPT,
    max_output_tokens=prompt.MAX_OUTPUT_TOKENS,
)


@dataclass(frozen=True)
class ExtractionOutcome:
    extraction: ResumeExtraction | None
    notice: str | None
    from_cache: bool = False


class ResumeExtractionService:
    """LLM resume extraction. On any problem returns no extraction plus a notice, and the caller
    falls back to the heuristic parser."""

    def __init__(self, session: Session, provider: AIProvider | None, settings: Settings) -> None:
        self._runner = LLMRunner(session, provider, settings)

    def extract(self, user_id: uuid.UUID, text: str, *, consent: bool) -> ExtractionOutcome:
        outcome = self._runner.run(
            user_id,
            TASK,
            prompt=prompt.build_prompt(text),
            schema=ResumeExtraction,
            cache_key=hashlib.sha256(text.encode()).hexdigest(),
            consent=consent,
        )
        notice = _NOTICES.get(outcome.notice, outcome.notice) if outcome.notice else None
        return ExtractionOutcome(outcome.value, notice, outcome.from_cache)
