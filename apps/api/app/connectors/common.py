"""Small helpers shared by connectors."""

import re
from datetime import UTC, datetime
from typing import Any

from app.services.jobs.normalize import EmploymentType
from app.utils.salary import Period, Salary

SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")

_EMPLOYMENT = {
    "fulltime": "full_time", "full-time": "full_time", "full_time": "full_time",
    "permanent": "full_time",
    "parttime": "part_time", "part-time": "part_time", "part_time": "part_time",
    "intern": "internship", "internship": "internship",
    "contract": "contract", "contractor": "contract", "fixed-term": "contract",
    "temporary": "contract",
    "freelance": "contract",
}  # fmt: skip


def employment(value: Any) -> EmploymentType | None:
    if not isinstance(value, str):
        return None
    return _EMPLOYMENT.get(value.strip().lower().replace(" ", ""))  # type: ignore[return-value]


def parse_time(value: Any) -> datetime | None:
    """ISO strings (naive treated as UTC), or epoch seconds/milliseconds."""
    if isinstance(value, int | float) or (isinstance(value, str) and value.isdigit()):
        seconds = float(value)
        if seconds > 1e12:
            seconds /= 1000
        return datetime.fromtimestamp(seconds, UTC)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def structured_salary(
    low: Any, high: Any, currency: Any, period: Period, text: str | None = None
) -> Salary | None:
    """A salary stated as structured fields. Zero or missing values mean "not listed"."""
    try:
        lo = int(float(low)) if low not in (None, "") else None
        hi = int(float(high)) if high not in (None, "") else None
    except (TypeError, ValueError):
        return None
    lo = lo if lo and lo > 0 else None
    hi = hi if hi and hi > 0 else None
    cur = str(currency or "").upper()[:3]
    if (lo is None and hi is None) or len(cur) != 3 or (lo and hi and hi < lo):
        return None
    shown = text or f"{cur} {lo or ''}{' - ' if lo and hi else ''}{hi or ''}".strip()
    return Salary(min=lo, max=hi, currency=cur, period=period, text=shown[:300])


def https_or_none(url: Any) -> str | None:
    return url if isinstance(url, str) and url.startswith("https://") else None
