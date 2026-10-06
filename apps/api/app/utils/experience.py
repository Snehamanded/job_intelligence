"""Years-of-experience requirements from job text."""

import re

_YEARS = r"(?:years?|yrs?)"
_RANGE = re.compile(
    rf"(?P<a>\d{{1,2}})\s*\+?\s*(?:-|–|—|to)\s*(?P<b>\d{{1,2}})\s*\+?\s*{_YEARS}", re.IGNORECASE
)
_MIN_WORD = re.compile(
    rf"(?:minimum|min\.?|at\s+least)\s*(?:of\s*)?(?P<a>\d{{1,2}})\s*\+?\s*{_YEARS}", re.IGNORECASE
)
_PLUS = re.compile(rf"(?P<a>\d{{1,2}})\s*(?:\+|plus)\s*{_YEARS}", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.;\n]")
_PLAIN = re.compile(rf"(?P<a>\d{{1,2}})\s*{_YEARS}", re.IGNORECASE)


def parse_experience(text: str) -> tuple[int | None, int | None]:
    """(min_years, max_years) from the first requirement that mentions experience."""
    candidates: list[tuple[int, int, int | None]] = []
    for pattern in (_RANGE, _MIN_WORD, _PLUS, _PLAIN):
        for m in pattern.finditer(text):
            # "experience" must be in the same sentence; bare "N years" must be followed by it.
            after = _SENTENCE_END.split(text[m.end() : m.end() + 80], maxsplit=1)[0].lower()
            before = _SENTENCE_END.split(text[max(0, m.start() - 40) : m.start()])[-1].lower()
            if "experience" not in after and (pattern is _PLAIN or "experience" not in before):
                continue
            low = int(m.group("a"))
            high = int(m.group("b")) if "b" in m.groupdict() and m.group("b") else None
            if low > 30 or (high is not None and (high < low or high > 40)):
                continue
            candidates.append((m.start(), low, high))
    if not candidates:
        return None, None
    _, low, high = min(candidates, key=lambda c: (c[0], c[2] is None))
    return low, high
