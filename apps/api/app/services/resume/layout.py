"""The visual layout of a PDF resume: lines of styled text pieces, rules and links, by position.

Used to re-render a tailored resume in the same format as the original. The PDF was validated at
upload; extraction is still bounded (pages) and any failure returns None, so callers fall back to
the template renderer.
"""

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import pdfplumber

logger = logging.getLogger(__name__)

Family = Literal["serif", "sans"]
BULLETS = {"•", "●", "▪", "◦", "○", "■", "‣", "∙", "·", "–", "-", "*", "➢", "►", "✓"}
_SANS = ("SANS", "HELV", "ARIAL", "CALIBRI", "VERDANA", "ROBOTO", "OPENSANS", "LATO", "INTER",
         "SEGOE", "CMSS", "SFSS")  # fmt: skip
_SUBSET = re.compile(r"^[A-Z]{6}\+")


@dataclass(frozen=True)
class Style:
    family: Family
    bold: bool
    italic: bool
    caps: bool
    size: float
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class Piece:
    """A run of text in one style, as drawn (a word, or a word part where the font changes)."""

    text: str
    x0: float
    x1: float
    style: Style
    dy: float = 0.0  # own baseline minus the line's (bullets often sit higher)


@dataclass
class Line:
    page: int
    baseline: float
    pieces: list[Piece]
    bullet: Piece | None = None

    @property
    def x0(self) -> float:
        return self.pieces[0].x0

    @property
    def x1(self) -> float:
        return self.pieces[-1].x1

    @property
    def size(self) -> float:
        sizes: dict[float, int] = {}
        for p in self.pieces:
            sizes[p.style.size] = sizes.get(p.style.size, 0) + len(p.text)
        return max(sizes, key=lambda s: sizes[s])

    def segments(self) -> list[list[Piece]]:
        """Pieces split at wide gaps: e.g. a title on the left and its date on the right."""
        out: list[list[Piece]] = [[self.pieces[0]]]
        for prev, piece in zip(self.pieces, self.pieces[1:], strict=False):
            if piece.x0 - prev.x1 > 4 * piece.style.size:
                out.append([])
            out[-1].append(piece)
        return out

    @property
    def text(self) -> str:
        return join_pieces(self.pieces)


@dataclass
class Rule:
    page: int
    x0: float
    x1: float
    y: float
    width: float
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class Link:
    page: int
    x0: float
    x1: float
    top: float
    bottom: float
    uri: str


@dataclass
class Layout:
    width: float
    height: float
    page_count: int
    lines: list[Line] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)


def join_pieces(pieces: list[Piece]) -> str:
    out = ""
    for prev, piece in zip([None, *pieces], pieces, strict=False):
        if prev is not None and piece.x0 - prev.x1 > 0.12 * piece.style.size:
            out += " "
        out += piece.text
    return out


def rgb(color: object) -> tuple[float, float, float]:
    """PDF gray, RGB or CMYK color as RGB 0..1; black when unknown (e.g. patterns)."""
    if isinstance(color, int | float):
        color = (color,)
    if not isinstance(color, list | tuple) or not all(isinstance(c, int | float) for c in color):
        return (0.0, 0.0, 0.0)
    v = [min(1.0, max(0.0, float(c))) for c in color]
    if len(v) == 1:
        return (v[0], v[0], v[0])
    if len(v) == 3:
        return (v[0], v[1], v[2])
    if len(v) == 4:
        c, m, y, k = v
        return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    return (0.0, 0.0, 0.0)


def style_of(fontname: str, size: float, color: object = None) -> Style:
    name = _SUBSET.sub("", fontname)
    upper = name.upper()
    sans = any(k in upper for k in _SANS)
    bold = bool(
        re.search(r"BOLD|BLACK|HEAVY|SEMIBOLD|DEMI|^CMBX|^CMB\d|^SFBX|^CMSSBX|-B$|,B", upper)
    )
    italic = bool(re.search(r"ITALIC|OBLIQUE|^CMTI|^CMBXTI|^CMSL|^SFTI|^SFSL|-I$|-BI$|,I", upper))
    caps = bool(re.search(r"^CMCSC|^SFCC|SMALLCAPS|ROMANCAPS|-SC$", upper))
    return Style("sans" if sans else "serif", bold, italic, caps, round(size, 1), rgb(color))


def extract_layout(data: bytes, max_pages: int = 4) -> Layout | None:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if not pdf.pages or len(pdf.pages) > max_pages:
                return None
            first = pdf.pages[0]
            layout = Layout(float(first.width), float(first.height), len(pdf.pages))
            for index, page in enumerate(pdf.pages):
                _read_page(layout, index, page)
    except Exception:  # malformed PDFs: fall back to the template
        logger.warning("layout_extraction_failed")
        return None
    return layout if layout.lines else None


def _read_page(layout: Layout, index: int, page: pdfplumber.page.Page) -> None:
    words = page.extract_words(extra_attrs=["fontname", "size"], x_tolerance=1.5,
                               keep_blank_chars=False, use_text_flow=False,
                               return_chars=True)  # fmt: skip
    height = float(page.height)
    for word in words:
        # The true baseline, from the text matrix ("bottom" includes the font's descent).
        word["baseline"] = height - float(word["chars"][0]["matrix"][5])
    rows: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda w: (float(w["baseline"]), float(w["x0"]))):
        # Bullets and symbols from other fonts sit a point or two off the text baseline.
        if rows and abs(float(word["baseline"]) - float(rows[-1][-1]["baseline"])) <= 2.5:
            rows[-1].append(word)
        else:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda w: float(w["x0"]))
        # The line's baseline: the lowest among its full-size pieces.
        main = max(float(w["size"]) for w in row)
        baseline = max(float(w["baseline"]) for w in row if float(w["size"]) >= main - 0.5)
        pieces = [
            Piece(str(w["text"]), float(w["x0"]), float(w["x1"]),
                  style_of(str(w["fontname"]), float(w["size"]),
                           w["chars"][0].get("non_stroking_color")),
                  round(float(w["baseline"]) - baseline, 2))
            for w in row
        ]  # fmt: skip
        bullet = None
        if len(pieces) > 1 and pieces[0].text in BULLETS and pieces[1].x0 - pieces[0].x1 > 1.5:
            bullet = pieces.pop(0)
        layout.lines.append(Line(index, baseline, pieces, bullet))
    for edge in [*page.lines, *page.rects]:
        height = abs(float(edge["bottom"]) - float(edge["top"]))
        width = float(edge["x1"]) - float(edge["x0"])
        if height <= 2 and width > 40:  # horizontal rules only
            layout.rules.append(
                Rule(index, float(edge["x0"]), float(edge["x1"]),
                     (float(edge["top"]) + float(edge["bottom"])) / 2,
                     max(height, float(edge.get("linewidth") or 0.4)),
                     rgb(edge.get("stroking_color") if edge["object_type"] == "line"
                         else edge.get("non_stroking_color")))
            )  # fmt: skip
    for link in page.hyperlinks:
        uri = str(link.get("uri") or "")
        if uri.startswith(("https://", "http://", "mailto:", "tel:")):
            layout.links.append(
                Link(index, float(link["x0"]), float(link["x1"]), float(link["top"]),
                     float(link["bottom"]), uri)
            )  # fmt: skip


def layout_text(layout: Layout) -> str:
    """Plain text, line by line, with the spaces LaTeX leaves implicit at font changes."""
    out: list[str] = []
    page = 0
    for line in sorted(layout.lines, key=lambda ln: (ln.page, ln.baseline)):
        if line.page != page:
            out.append("")
            page = line.page
        text = " ".join(join_pieces(seg) for seg in line.segments())
        out.append(f"{line.bullet.text} {text}" if line.bullet else text)
    return "\n".join(out)
