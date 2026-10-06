"""Deterministic parsing of resume date ranges and experience length."""

import re
from dataclasses import dataclass
from datetime import date

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_CURRENT = {"present", "current", "now", "till date", "to date", "ongoing", "today"}

_MONTH_NAME = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*\.?"
_POINT = (
    rf"(?:{_MONTH_NAME}\s*,?\s*'?\d{{2,4}}"  # Jan 2023, January, 2023, Jan '23
    r"|\d{1,2}\s*[/.-]\s*\d{4}"  # 01/2023, 1.2023
    r"|\d{4}\s*[/.-]\s*\d{1,2}(?!\d)"  # 2023-01
    r"|\d{4})"  # 2023
)
_END = rf"(?:{_POINT}|present|current|now|till date|to date|ongoing|today)"
DATE_RANGE_RE = re.compile(
    rf"(?P<start>{_POINT})\s*(?:-|–|—|to|until|till)\s*(?P<end>{_END})", re.IGNORECASE
)


@dataclass(frozen=True, order=True)
class YearMonth:
    year: int
    month: int

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    def index(self) -> int:
        return self.year * 12 + (self.month - 1)

    @classmethod
    def parse(cls, value: str) -> "YearMonth":
        year, month = value.split("-")
        return cls(int(year), int(month))


@dataclass(frozen=True)
class DateRange:
    start: YearMonth
    end: YearMonth | None  # None means "present"
    approximate: bool  # a side had only a year

    @property
    def is_current(self) -> bool:
        return self.end is None


def _year(raw: str) -> int | None:
    value = int(raw)
    if len(raw) == 2:
        value += 2000 if value < 70 else 1900
    return value if 1950 <= value <= 2100 else None


def parse_point(text: str) -> tuple[YearMonth, bool] | None:
    """Parse one date. Returns (value, year_only)."""
    s = text.strip().lower().replace(",", " ").replace("'", " ")
    m = re.fullmatch(rf"({_MONTH_NAME})\s*(\d{{2,4}})", s)
    if m:
        month = _MONTHS.get(m.group(1)[:3])
        year = _year(m.group(2))
        return (YearMonth(year, month), False) if month and year else None
    m = re.fullmatch(r"(\d{1,2})\s*[/.-]\s*(\d{4})", s)
    if m:
        month, year = int(m.group(1)), _year(m.group(2))
        return (YearMonth(year, month), False) if year and 1 <= month <= 12 else None
    m = re.fullmatch(r"(\d{4})\s*[/.-]\s*(\d{1,2})", s)
    if m:
        year, month = _year(m.group(1)), int(m.group(2))
        return (YearMonth(year, month), False) if year and 1 <= month <= 12 else None
    m = re.fullmatch(r"\d{4}", s)
    if m:
        year = _year(s)
        return (YearMonth(year, 1), True) if year else None
    return None


def parse_date_range(text: str | None, today: date | None = None) -> DateRange | None:
    if not text:
        return None
    m = DATE_RANGE_RE.search(text)
    if not m:
        return None
    start = parse_point(m.group("start"))
    if start is None:
        return None
    end_raw = m.group("end").strip().lower()
    if end_raw in _CURRENT:
        return DateRange(start[0], None, start[1])
    end = parse_point(end_raw)
    if end is None:
        return None
    end_value = end[0]
    if end[1]:
        # "2021 - 2022": count the end year as ending in December only if it's the start year.
        end_value = YearMonth(end_value.year, 12 if end_value.year == start[0].year else 1)
    if end_value < start[0]:
        return None
    today = today or date.today()
    if start[0] > YearMonth(today.year, today.month):
        return None
    return DateRange(start[0], end_value, start[1] or end[1])


def experience_months(ranges: list[DateRange], today: date | None = None) -> int:
    """Total months covered by the ranges, counting overlapping roles once."""
    today = today or date.today()
    now = YearMonth(today.year, today.month)
    intervals: list[tuple[int, int]] = []
    for r in ranges:
        end = r.end if r.end is not None and r.end <= now else now
        if r.start > end:
            continue
        # Month ranges count inclusively (Jan-Mar is 3 months); year-only ranges don't
        # ("2019 - 2023" is 48 months, not 49).
        inclusive = 0 if r.approximate and r.end is not None else 1
        intervals.append((r.start.index(), end.index() + inclusive))
    intervals.sort()
    total = 0
    merged: tuple[int, int] | None = None
    for lo, hi in intervals:
        if merged is None or lo > merged[1]:
            if merged is not None:
                total += merged[1] - merged[0]
            merged = (lo, hi)
        else:
            merged = (merged[0], max(merged[1], hi))
    if merged is not None:
        total += merged[1] - merged[0]
    return total
