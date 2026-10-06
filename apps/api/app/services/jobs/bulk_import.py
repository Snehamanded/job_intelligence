"""Bulk import of job posts pasted from alert emails or a WhatsApp chat export.

With AI consent, the LLM locates each post by quoting its first and last words; the post is then
sliced from the pasted text in code, and its title, company, location and link must appear in that
slice. Without AI (or if the call fails) a rule-based split is used. Links to company career pages
are imported in full; sites that forbid automated access (LinkedIn, Naukri, ...) are only linked.
"""

import hashlib
import logging
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.prompts import job_posts as prompt
from app.ai.providers import AIProvider
from app.ai.schemas import FoundJobPosts
from app.ai.services.runner import LLMRunner, LLMTask
from app.connectors.registry import Connectors
from app.core.config import Settings
from app.models import ImportBatch
from app.repositories.settings import SettingsRepository
from app.services.jobs.importer import ImportRejectedError, JobImporter, restricted_site
from app.services.jobs.normalize import RawPosting, normalize
from app.services.jobs.store import JobStore

logger = logging.getLogger(__name__)

MAX_CHARS = 60_000
CHUNK_CHARS = 12_000
MAX_POSTS = 60
MAX_FETCHES = 15
SOURCES = {"email": "email_alert", "whatsapp": "whatsapp", "other": "pasted"}
SHORT_NOTE = (
    "Only a short summary was in the message. Paste the full description for a more accurate match."
)

TASK = LLMTask(prompt.TASK, prompt.PROMPT_VERSION, prompt.SYSTEM_PROMPT, prompt.MAX_OUTPUT_TOKENS)

_URL = re.compile(r"https?://[^\s<>\"')\]]+")
# WhatsApp export lines: "12/10/25, 9:41 am - Name: text" (Android) or
# "[12/10/25, 9:41:03 AM] Name: text" (iOS).
_WA_HEADER = re.compile(
    r"^\[?\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s?[apAP]\.?\s?[mM]\.?)?\]?"
    r"\s*(?:-\s*)?(?:(?P<sender>[^:\n]{1,80}?):\s)?(?P<body>.*)$"
)
_WA_SKIP = re.compile(
    r"<media omitted>|<attached:|this message was deleted|you deleted this message|"
    r"(image|video|audio|sticker|document|gif) omitted|messages and calls are end-to-end",
    re.IGNORECASE,
)
_ROLE = re.compile(
    r"\b(engineer|developer|analyst|manager|intern|internship|designer|scientist|architect|"
    r"consultant|specialist|executive|associate|administrator|tester|qa|lead|devops|sde|"
    r"programmer|officer|trainee|fresher)s?\b",
    re.IGNORECASE,
)
_JOBBY = re.compile(r"\b(hiring|opening|vacanc|position|role|apply|job|walk-?in|ctc|lpa)", re.I)
_COMPANY = [
    re.compile(r"(?:company|organi[sz]ation|employer)\s*[:\-–]\s*(?P<v>[^\n|,]{2,60})", re.I),
    re.compile(r"^(?P<v>[A-Z][\w&.\- ]{1,50}?)\s+is\s+hiring", re.M),
    re.compile(r"hiring\s+(?:at|@)\s+(?P<v>[A-Z][\w&.\-]{1,40}(?: [A-Z][\w&.\-]{1,40}){0,3})"),
]
_LOCATION = re.compile(r"(?:location|loc|place|city)\s*[:\-–]\s*(?P<v>[^\n|]{2,80})", re.I)


@dataclass
class Post:
    text: str
    title: str
    company: str | None = None
    location: str | None = None
    url: str | None = None


# --- text preparation ------------------------------------------------------------------------


def clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u202f", " ").replace("\u00a0", " ")
    return re.sub("[\u200e\u200f\u200b\ufeff]", "", text)


def limit(text: str, channel: str) -> tuple[str, bool]:
    """At most MAX_CHARS, cut at a line: the newest messages of a chat export, else the start."""
    if len(text) <= MAX_CHARS:
        return text, False
    if channel == "whatsapp":
        tail = text[-MAX_CHARS:]
        return tail[tail.find("\n") + 1 :], True
    head = text[:MAX_CHARS]
    return (head[: head.rfind("\n")] if "\n" in head else head), True


def whatsapp_messages(text: str) -> list[str] | None:
    """Messages of a chat export, without timestamps or sender names; None if not an export."""
    lines = text.split("\n")
    if sum(1 for line in lines if _WA_HEADER.match(line)) < 2:
        return None
    messages: list[list[str]] = []
    for line in lines:
        m = _WA_HEADER.match(line)
        if m:
            # Lines without a sender are system notices ("X joined", encryption notice).
            messages.append([m["body"]] if m["sender"] else [])
        elif messages:
            messages[-1].append(line)
    out = []
    for parts in messages:
        body = "\n".join(parts).strip()
        if body and not _WA_SKIP.search(body):
            out.append(body)
    return out


def _flat(text: str) -> tuple[str, list[int]]:
    """Lower-cased text with whitespace runs collapsed and formatting marks (WhatsApp *bold*,
    _italic_, ~strike~, `code`) dropped, and each character's original index."""
    chars: list[str] = []
    index: list[int] = []
    space = False
    for i, ch in enumerate(text):
        if ch in "*_~`":
            continue
        if ch.isspace():
            if chars and not space:
                chars.append(" ")
                index.append(i)
            space = True
        else:
            chars.append(ch.lower())
            index.append(i)
            space = False
    return "".join(chars), index


def contains(haystack: str, needle: str) -> bool:
    n = _flat(needle)[0].strip()
    return bool(n) and n in _flat(haystack)[0]


def locate(text: str, start: str, end: str) -> tuple[int, int] | None:
    flat, index = _flat(text)
    s, e = _flat(start)[0].strip(), _flat(end)[0].strip()
    if not s or not e:
        return None
    a = flat.find(s)
    if a < 0:
        return None
    b = flat.find(e, a)
    if b < 0:
        return None
    return index[a], index[b + len(e) - 1] + 1


def chunks(text: str) -> list[str]:
    out: list[str] = []
    current = ""
    for block in re.split(r"\n\s*\n", text):
        if current and len(current) + len(block) > CHUNK_CHARS:
            out.append(current)
            current = ""
        current = f"{current}\n\n{block}" if current else block
    if current.strip():
        out.append(current)
    return out


# --- finding posts ------------------------------------------------------------------------------


def posts_from_ai(chunk: str, found: FoundJobPosts) -> list[Post]:
    posts: list[Post] = []
    for p in found.posts:
        span = locate(chunk, p.start_quote, p.end_quote)
        if span is None:
            continue
        text = chunk[span[0] : span[1]].strip()
        if not contains(text, p.title):
            continue
        url = p.url if p.url and p.url in text and _URL.fullmatch(p.url) else None
        posts.append(
            Post(
                text=text,
                title=p.title,
                company=p.company if p.company and contains(text, p.company) else None,
                location=p.location if p.location and contains(text, p.location) else None,
                url=url or first_url(text),
            )
        )
    return posts


def first_url(text: str) -> str | None:
    m = _URL.search(text)
    return m.group(0).rstrip(".,;:!") if m else None


_HIRING_PREFIX = re.compile(
    r"^(?:we\s+are\s+|we're\s+)?(?:urgently\s+)?hiring\s*(?:for)?\s*[:\-–!]*\s*", re.I
)
_TITLE_PATTERNS = [
    re.compile(
        r"(?:role|position|designation|job\s*title|opening)\s*[:\-–]\s*(?P<v>[^\n|]{3,100})",
        re.I,
    ),
    re.compile(
        r"\bis\s+hiring\s+(?:an?\s+|for\s+(?:an?\s+)?)?(?P<v>[^.,!\n]{3,80}?)"
        r"(?=\s+(?:in|at|for|-)\s|[.,!\n]|$)",
        re.I,
    ),
]


def _title(candidate: str, lines: list[str]) -> str:
    for pattern in _TITLE_PATTERNS:
        if m := pattern.search(candidate):
            return m["v"].strip()[:200]
    line = next((ln for ln in lines if _ROLE.search(ln) and len(ln) <= 100), lines[0])
    return (_HIRING_PREFIX.sub("", line).strip(" :-–*") or line)[:200]


def rule_posts(text: str, messages: list[str] | None) -> list[Post]:
    """Without AI: chat messages are posts; email text is split into blocks ending at a link."""
    if messages is not None:
        candidates = messages
    else:
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
        candidates, pending = [], []
        has_links = any(_URL.search(b) for b in blocks)
        for block in blocks:
            if has_links and not _URL.search(block):
                pending.append(block)
                continue
            # An alert's job block holds title, company and link together; a link alone belongs
            # to the text before it.
            text_lines = [ln for ln in block.split("\n") if ln.strip() and not _URL.search(ln)]
            candidates.append(block if len(text_lines) >= 2 else "\n\n".join([*pending, block]))
            pending = []
    posts = []
    for candidate in candidates:
        lines = [ln.strip(" *_•-–\t") for ln in candidate.split("\n") if ln.strip(" *_•-–\t")]
        if len(candidate) < 30 or not lines:
            continue
        if not (_ROLE.search(candidate) and (_URL.search(candidate) or _JOBBY.search(candidate))):
            continue
        title = _title(candidate, lines)
        company = next((m["v"].strip() for r in _COMPANY if (m := r.search(candidate))), None)
        if company is None and len(lines) >= 3 and lines[0] == title and len(lines[1]) <= 60:
            company = lines[1] if not _URL.search(lines[1]) else None  # alert: title, company
        location = (m["v"].strip() if (m := _LOCATION.search(candidate)) else None) or (
            lines[2] if company and len(lines) >= 4 and len(lines[2]) <= 60
            and not _URL.search(lines[2]) and lines[1] == company else None
        )  # fmt: skip
        posts.append(Post(candidate, title, company, location, first_url(candidate)))
    return posts


# --- the batch --------------------------------------------------------------------------------


class BulkImporter:
    def __init__(
        self,
        session: Session,
        provider: AIProvider | None,
        settings: Settings,
        connectors: Connectors,
        user_id: uuid.UUID,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._session = session
        self._settings = settings
        self._user_id = user_id
        self._runner = LLMRunner(session, provider, settings)
        self._importer = JobImporter(session, user_id, connectors)
        self._store = JobStore(session, user_id)
        self._sleep = sleep

    def find(self, text: str, channel: str) -> tuple[list[Post], str, str | None]:
        """Posts, the method used ("ai" or "rules") and a notice when AI wasn't used."""
        text = clean(text)
        messages = whatsapp_messages(text) if channel != "email" else None
        body = "\n\n".join(messages) if messages is not None else text
        user_settings = SettingsRepository(self._session).get_for_user(self._user_id)
        consent = bool(user_settings and user_settings.llm_consent)
        posts: list[Post] = []
        notice = None
        method = "ai"
        for chunk in chunks(body):
            outcome = self._runner.run(
                self._user_id, TASK, prompt=prompt.build_prompt(chunk), schema=FoundJobPosts,
                cache_key=hashlib.sha256(chunk.encode()).hexdigest(), consent=consent,
            )  # fmt: skip
            if outcome.value is None:
                notice, method = outcome.notice, "rules"
                return rule_posts(body, messages)[:MAX_POSTS], method, notice
            posts += posts_from_ai(chunk, outcome.value)
        return posts[:MAX_POSTS], method, notice

    def save(self, post: Post, channel: str, fetches: list[int]) -> dict[str, Any]:
        result: dict[str, Any] = {"title": post.title, "company": post.company, "url": post.url,
                                  "job_id": None, "status": "new", "note": None}  # fmt: skip
        if post.url and restricted_site(post.url) is None and fetches[0] < MAX_FETCHES:
            fetches[0] += 1
            if fetches[0] > 1:
                self._sleep(self._settings.connector_request_delay_seconds)
            try:
                job = self._importer.from_url(post.url)
                result.update(job_id=str(job.id), status="imported", title=job.title,
                              company=job.company, note="Read in full from its link.")  # fmt: skip
                return result
            except ImportRejectedError:
                self._session.rollback()  # fall back to the message's own text
        key = f"{post.title}|{post.company}|{post.text}"
        raw = RawPosting(
            source=SOURCES[channel],
            source_job_id=hashlib.sha256(key.encode()).hexdigest()[:32],
            title=post.title,
            company=post.company or "Unknown company",
            location_text=post.location or "",
            description_text=post.text,
            url=post.url,
        )
        saved = self._store.save(normalize(raw))
        self._session.commit()
        result.update(job_id=str(saved.job.id), status=saved.outcome)
        if len(post.text) < 300:
            result["note"] = SHORT_NOTE
        return result

    def run(self, batch_id: uuid.UUID) -> None:
        batch = self._session.scalar(
            select(ImportBatch).where(
                ImportBatch.id == batch_id, ImportBatch.user_id == self._user_id
            )
        )
        if batch is None or batch.pasted_text is None:
            return
        batch.status = "running"
        self._session.commit()
        posts, batch.method, notice = self.find(batch.pasted_text, batch.channel)
        batch.notice = " ".join(n for n in (batch.notice, notice) if n) or None
        self._session.commit()  # a failed link import below rolls back uncommitted changes
        fetches = [0]
        results = []
        for post in posts:
            try:
                results.append(self.save(post, batch.channel, fetches))
            except Exception:
                self._session.rollback()
                logger.exception("import_post_failed", extra={"import_batch_id": str(batch_id)})
                results.append({"title": post.title, "company": post.company, "url": post.url,
                                "job_id": None, "status": "failed",
                                "note": "This post couldn't be imported."})  # fmt: skip
        batch.results = results
        batch.status = "completed"
        batch.pasted_text = None  # may hold other people's names and numbers: don't keep it
        batch.finished_at = datetime.now(UTC)
        if not posts:
            batch.error_message = "No job posts were found in the pasted text."
        self._session.commit()
        logger.info(
            "import_batch_completed",
            extra={"import_batch_id": str(batch_id), "method": batch.method, "posts": len(posts),
                   "fetched": fetches[0]},
        )  # fmt: skip
