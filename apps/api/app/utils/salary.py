"""Salary parsing from job text. Never guesses: no currency or ambiguous period means unknown."""

import re
from dataclasses import dataclass
from typing import Literal

Period = Literal["year", "month", "hour"]

_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "rs": "INR", "rs.": "INR"}
_CODES = {"USD", "EUR", "GBP", "INR", "CAD", "AUD", "SGD", "AED", "JPY", "CHF", "NZD", "SEK", "PLN"}
_MULTIPLIERS = {"k": 1_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000,
                "l": 100_000, "lpa": 100_000, "cr": 10_000_000, "crore": 10_000_000,
                "crores": 10_000_000}  # fmt: skip
# Below these annual amounts, an unlabelled figure is not clearly annual, so we don't assume.
_ANNUAL_FLOOR = {"INR": 300_000, "JPY": 2_000_000}
_DEFAULT_ANNUAL_FLOOR = 20_000

_CONTEXT = re.compile(
    r"salary|pay\b|pay range|compensation|\bctc\b|package|stipend|remuneration|base pay|\bote\b|"
    r"\blpa\b|per annum|wage",
    re.IGNORECASE,
)
_UP_TO = re.compile(r"up\s*to|upto|max(?:imum)?\.?", re.IGNORECASE)
_CUR = r"(?:[$€£₹]|rs\.?|usd|eur|gbp|inr|cad|aud|sgd|aed|jpy|chf|nzd|sek|pln)"
_NUM = r"\d[\d,.]*"
_MULT = r"(?:k|lakhs?|lacs?|lpa|l|crores?|cr)\b"
_PERIOD = (
    r"(?P<period>per\s+annum|per\s+year|a\s+year|/\s*year|/\s*yr|annually|annual|p\.?a\.?|"
    r"per\s+month|a\s+month|/\s*month|/\s*mo|monthly|per\s+hour|an\s+hour|/\s*hour|/\s*hr|hourly)"
)
_AMOUNT = re.compile(
    rf"(?P<c1>{_CUR})?\s?(?P<a>{_NUM})\s?(?P<m1>{_MULT})?"
    rf"(?:\s*(?:-|–|—|to)\s*(?P<c2>{_CUR})?\s?(?P<b>{_NUM})\s?(?P<m2>{_MULT})?)?"
    rf"(?:\s*(?P<code>{_CUR}))?(?:\s*{_PERIOD})?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Salary:
    min: int | None
    max: int | None
    currency: str
    period: Period
    text: str


def _currency(token: str | None) -> str | None:
    if not token:
        return None
    t = token.strip().lower()
    if t in _SYMBOLS:
        return _SYMBOLS[t]
    return t.upper() if t.upper() in _CODES else None


def _number(raw: str, multiplier: int) -> float | None:
    raw = raw.strip(".,")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):  # 71.000 (European thousands)
        raw = raw.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?", raw):  # 1,20,000 or 139,200
        raw = raw.replace(",", "")
    elif not re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return None
    try:
        return float(raw) * multiplier
    except ValueError:
        return None


def _period(raw: str | None) -> Period | None:
    if not raw:
        return None
    r = raw.lower()
    if "hour" in r or "hr" in r:
        return "hour"
    if "month" in r or "mo" in r.replace("/", "").strip():
        return "month"
    return "year"


def parse_salary(text: str) -> Salary | None:
    for match in _AMOUNT.finditer(text):
        # Only amounts that read like pay: a salary keyword shortly before, or LPA-style units.
        window = text[max(0, match.start() - 120) : match.end() + 20]
        units = (match.group("m1") or match.group("m2") or "").lower()
        if not _CONTEXT.search(window) and units not in {"lpa"}:
            continue
        currency = (
            _currency(match.group("c1"))
            or _currency(match.group("c2"))
            or _currency(match.group("code"))
            or (
                "INR"
                if units in {"lpa", "lakh", "lakhs", "lac", "lacs", "l", "cr", "crore", "crores"}
                else None
            )
        )
        if currency is None:
            continue
        m1 = _MULTIPLIERS.get((match.group("m1") or match.group("m2") or "").lower(), 1)
        m2 = _MULTIPLIERS.get((match.group("m2") or match.group("m1") or "").lower(), 1)
        low: float | None = _number(match.group("a"), m1)
        high = _number(match.group("b"), m2) if match.group("b") else None
        if low is None or (match.group("b") and high is None):
            continue
        if low < 1 or (high is not None and high < low):
            continue
        period = _period(match.group("period"))
        if units == "lpa":
            period = "year"
        if period is None:
            floor = _ANNUAL_FLOOR.get(currency, _DEFAULT_ANNUAL_FLOOR)
            if low < floor:
                continue  # an unlabelled small figure could be monthly or hourly; don't guess
            period = "year"
        if high is None and _UP_TO.search(text[max(0, match.start() - 15) : match.start()]):
            low, high = None, low  # "up to X" is a ceiling, not a floor
        return Salary(
            min=round(low) if low is not None else None,
            max=round(high) if high is not None else None,
            currency=currency,
            period=period,
            text=" ".join(match.group(0).split())[:300],
        )
    return None


def annualize(amount: int, period: Period) -> int:
    return {"year": amount, "month": amount * 12, "hour": amount * 2080}[period]
