import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"[ \t  -​　]+")
_MANY_NEWLINES = re.compile(r"\n{3,}")

# Characters treated as equal when matching quotes against the resume.
_EQUIVALENT = str.maketrans(
    {
        "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "•": " ", "●": " ", "▪": " ", "·": " ", "‣": " ", "⁃": " ",
    }
)  # fmt: skip

BULLET_CHARS = "•●▪·‣⁃-*–—◦"


def normalize_text(text: str) -> str:
    """Canonical form for extracted resume text. Spans are offsets into this form."""
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    return _MANY_NEWLINES.sub("\n\n", "\n".join(lines)).strip()


class TextIndex:
    """Finds verbatim quotes in a text, tolerant only of case, whitespace and dash/quote style."""

    def __init__(self, text: str) -> None:
        self.text = text
        chars: list[str] = []
        positions: list[int] = []
        previous_space = True
        for i, ch in enumerate(text.translate(_EQUIVALENT).lower()):
            if ch.isspace():
                if previous_space:
                    continue
                ch = " "
                previous_space = True
            else:
                previous_space = False
            chars.append(ch)
            positions.append(i)
        self._folded = "".join(chars)
        self._positions = positions

    @staticmethod
    def fold(quote: str) -> str:
        folded = " ".join(quote.translate(_EQUIVALENT).lower().split())
        return folded

    def find(self, quote: str) -> tuple[int, int] | None:
        """Return [start, end) offsets of `quote` in the original text, or None."""
        needle = self.fold(quote.strip().lstrip(BULLET_CHARS).strip())
        if not needle:
            return None
        at = self._folded.find(needle)
        if at < 0:
            return None
        return self._positions[at], self._positions[at + len(needle) - 1] + 1

    def contains(self, quote: str) -> bool:
        return self.find(quote) is not None


def contains_folded(haystack: str, needle: str) -> bool:
    return TextIndex.fold(needle) in TextIndex.fold(haystack)
