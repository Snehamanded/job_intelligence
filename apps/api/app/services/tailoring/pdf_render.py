"""Tailored resume as a PDF, built on the server (so no browser header or footer).

When the uploaded resume is a PDF whose layout can be read, the result keeps its format: every
unchanged line is redrawn where it was, in the same style, and only what tailoring changed (reworded
bullets, bullet order, summary, skill order) is re-wrapped in the original paragraph's style, with
its bold phrases kept. Otherwise a classic one-column template is used.
"""

import difflib
import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from fpdf import FPDF

from app.schemas.tailoring import ResumeDocument
from app.services.resume.layout import Layout, Line, Piece, Rule, Style, join_pieces
from app.services.resume.layout import Link as LayoutLink
from app.services.tailoring.docx_render import education_line

logger = logging.getLogger(__name__)
FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
BLACK = (0.0, 0.0, 0.0)
ROUND_BULLETS = {"•", "●", "∙", "·"}

# Latin Modern: the open version of Computer Modern (LaTeX). Optical sizes where available.
_FONTS: dict[tuple[str, bool, bool], dict[int, str]] = {
    ("serif", False, False): {9: "lmroman9-regular", 10: "lmroman10-regular",
                              12: "lmroman12-regular", 17: "lmroman17-regular"},
    ("serif", True, False): {9: "lmroman9-bold", 10: "lmroman10-bold", 12: "lmroman12-bold"},
    ("serif", False, True): {9: "lmroman9-italic", 10: "lmroman10-italic",
                             12: "lmroman12-italic"},
    ("serif", True, True): {10: "lmroman10-bolditalic"},
    ("sans", False, False): {10: "lmsans10-regular"},
    ("sans", True, False): {10: "lmsans10-bold"},
    ("sans", False, True): {10: "lmsans10-oblique"},
    ("sans", True, True): {10: "lmsans10-boldoblique"},
}  # fmt: skip
_CAPS = "lmromancaps10-regular"


class Canvas:
    def __init__(self, width: float, height: float) -> None:
        self.pdf = FPDF(unit="pt", format=(width, height))
        self.pdf.set_auto_page_break(False)
        self.pdf.set_margins(0, 0, 0)
        self.pdf.set_creator("Job Intelligence")
        self.height = height
        self._loaded: set[str] = set()

    def font(self, style: Style) -> None:
        if style.caps:
            name = _CAPS
        else:
            sizes = _FONTS[(style.family, style.bold, style.italic)]
            name = sizes[min(sizes, key=lambda s: abs(s - style.size))]
        if name not in self._loaded:
            self.pdf.add_font(name, "", str(FONT_DIR / f"{name}.otf"))
            self._loaded.add(name)
        self.pdf.set_font(name, size=style.size)

    def width(self, text: str, style: Style) -> float:
        self.font(style)
        return float(self.pdf.get_string_width(text))

    def text(
        self, x: float, baseline: float, text: str, style: Style, fit: float | None = None
    ) -> None:
        """Draw text on a baseline; `fit` stretches it slightly to the original's width."""
        self.font(style)
        self.pdf.set_text_color(*(round(c * 255) for c in style.color))
        stretch = 100.0
        if fit:
            natural = float(self.pdf.get_string_width(text))
            if natural > 0:
                stretch = max(85.0, min(115.0, 100 * fit / natural))
        if stretch != 100.0:
            self.pdf.set_stretching(stretch)
        self.pdf.text(x, baseline, text)
        if stretch != 100.0:
            self.pdf.set_stretching(100)

    def rule(self, x0: float, x1: float, y: float, width: float, color: tuple[float, ...]) -> None:
        self.pdf.set_draw_color(*(round(c * 255) for c in color))
        self.pdf.set_line_width(width)
        self.pdf.line(x0, y, x1, y)

    def dot(self, x: float, y: float, diameter: float, color: tuple[float, ...]) -> None:
        self.pdf.set_fill_color(*(round(c * 255) for c in color))
        self.pdf.ellipse(x - diameter / 2, y - diameter / 2, diameter, diameter, style="F")

    def output(self) -> bytes:
        return bytes(self.pdf.output())


# --- wrapping styled text ------------------------------------------------------------------

Run = tuple[str, Style]


def styled_runs(text: str, base: Style, marks: list[tuple[str, Style]]) -> list[Run]:
    """`text` in `base`, with every whole-word occurrence of a marked phrase in its style."""
    styles = [base] * len(text)
    for phrase, style in sorted(marks, key=lambda m: -len(m[0])):
        for m in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text):
            if all(s == base for s in styles[m.start() : m.end()]):
                styles[m.start() : m.end()] = [style] * (m.end() - m.start())
    runs: list[Run] = []
    for ch, style in zip(text, styles, strict=True):
        if runs and runs[-1][1] == style:
            runs[-1] = (runs[-1][0] + ch, style)
        else:
            runs.append((ch, style))
    return runs


def _words(runs: list[Run]) -> list[list[Run]]:
    words: list[list[Run]] = [[]]
    for text, style in runs:
        for i, part in enumerate(re.split(r"\s+", text)):
            if i:
                words.append([])
            if part:
                words[-1].append((part, style))
    return [w for w in words if w]


def wrap(
    canvas: Canvas, runs: list[Run], width: float, base: Style
) -> list[tuple[list[list[Run]], float]]:
    """Greedy line breaking. Returns lines of words with each line's natural width."""
    space = canvas.width(" ", base)
    lines: list[tuple[list[list[Run]], float]] = []
    current: list[list[Run]] = []
    used = 0.0
    for word in _words(runs):
        w = sum(canvas.width(t, s) for t, s in word)
        if current and used + space + w > width:
            lines.append((current, used))
            current, used = [], 0.0
        used += (space if current else 0) + w
        current.append(word)
    if current:
        lines.append((current, used))
    return lines


def draw_paragraph(
    canvas: Canvas, runs: list[Run], x0: float, x1: float, baseline: float, pitch: float,
    base: Style, justify: bool,
) -> float:  # fmt: skip
    """Draw wrapped text from `baseline`; returns the last line's baseline."""
    lines = wrap(canvas, runs, x1 - x0, base)
    space = canvas.width(" ", base)
    y = baseline
    for n, (words, natural) in enumerate(lines):
        y = baseline + n * pitch
        gap = space
        if justify and n < len(lines) - 1 and len(words) > 1:
            gap = space + (x1 - x0 - natural) / (len(words) - 1)
        x = x0
        for word in words:
            for text, style in word:
                canvas.text(x, y, text, style)
                x += canvas.width(text, style)
            x += gap
    return y


# --- the original's layout as blocks ----------------------------------------------------------


@dataclass
class Block:
    page: int
    y: float  # original first baseline (or rule position)
    lines: list[Line] = field(default_factory=list)
    rule: Rule | None = None
    new_text: str | None = None  # replacement text, drawn in the lines' style
    # Space from the previous block's last baseline; None for a page's first block.
    gap: float | None = None

    @property
    def span(self) -> float:
        return self.lines[-1].baseline - self.lines[0].baseline if self.lines else 0.0

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _right_edges(layout: Layout) -> dict[int, float]:
    edges: dict[int, float] = {}
    for line in layout.lines:
        edges[line.page] = max(edges.get(line.page, 0.0), line.x1)
    return edges


def _continues(prev: Line, line: Line, first: Line, right: float) -> bool:
    if line.page != prev.page or line.bullet is not None:
        return False
    if len(line.segments()) > 1 or len(prev.segments()) > 1:
        return False
    if abs(line.x0 - first.x0) > 1.5 or abs(line.size - prev.size) > 0.6:
        return False
    if line.baseline - prev.baseline > 1.6 * prev.size:
        return False
    return prev.x1 >= right - 3 * prev.size  # the previous line was full, so text ran on


def blocks_of(layout: Layout) -> list[Block]:
    right = _right_edges(layout)
    blocks: list[Block] = []
    for line in sorted(layout.lines, key=lambda ln: (ln.page, ln.baseline)):
        prev = blocks[-1] if blocks else None
        if prev and _continues(prev.lines[-1], line, prev.lines[0], right[line.page]):
            prev.lines.append(line)
        else:
            blocks.append(Block(line.page, line.baseline, [line]))
    blocks += [Block(r.page, r.y, rule=r) for r in layout.rules]
    blocks.sort(key=lambda b: (b.page, b.y))
    for prev, block in zip([None, *blocks], blocks, strict=False):
        if prev is not None and prev.page == block.page:
            block.gap = block.y - (prev.y + prev.span)
    return blocks


_HEADING = re.compile(r"[A-Za-z][A-Za-z &/,'-]{1,40}")


def is_heading(block: Block, body: float) -> bool:
    if len(block.lines) != 1 or block.lines[0].bullet or len(block.lines[0].segments()) > 1:
        return False
    line = block.lines[0]
    if not _HEADING.fullmatch(line.text.strip()):
        return False
    style = line.pieces[0].style
    return (
        line.size > body + 0.4 or style.caps or line.text.isupper()
        or all(p.style.bold for p in line.pieces)
    )  # fmt: skip


def _body_size(layout: Layout) -> float:
    counts: dict[float, int] = {}
    for line in layout.lines:
        for p in line.pieces:
            counts[p.style.size] = counts.get(p.style.size, 0) + len(p.text)
    return max(counts, key=lambda s: counts[s])


def _section(blocks: list[Block], body: float, pattern: str) -> list[int] | None:
    """Indexes of the text blocks under the first heading matching `pattern`."""
    for i, block in enumerate(blocks):
        if block.lines and is_heading(block, body) and re.search(pattern, block.text, re.I):
            out = []
            for j in range(i + 1, len(blocks)):
                if blocks[j].lines and is_heading(blocks[j], body):
                    break
                if blocks[j].lines:
                    out.append(j)
                elif out:  # a rule after the section's text ends it
                    break
            return out
    return None


def _find(blocks: list[Block], text: str, used: set[int]) -> int | None:
    target = norm(text)
    if not target:
        return None
    best, best_ratio = None, 0.9
    for i, block in enumerate(blocks):
        if not block.lines or i in used:
            continue
        candidate = norm(block.text)
        if candidate == target:
            return i
        matcher = difflib.SequenceMatcher(None, candidate, target, autojunk=False)
        if matcher.real_quick_ratio() > best_ratio and matcher.ratio() > best_ratio:
            best, best_ratio = i, matcher.ratio()
    return best


def plan(layout: Layout, base: ResumeDocument, doc: ResumeDocument) -> list[Block] | None:
    """The original's blocks with the tailored changes applied, or None when one can't be placed."""
    blocks = blocks_of(layout)
    body = _body_size(layout)
    used: set[int] = set()
    # Bullets: reordered within their role's slots; reworded ones get new text.
    for base_role in base.experience:
        role = next((r for r in doc.experience if r.id == base_role.id), None)
        if role is None:
            continue
        ids = [b.id for b in base_role.bullets]
        if [b.id for b in role.bullets] == ids and not any(b.ai_changed for b in role.bullets):
            continue
        found: dict[str, int] = {}
        for bullet in base_role.bullets:
            index = _find(blocks, bullet.original_text, used)
            if index is None:
                _unplaced("bullet")
                return None
            found[bullet.id] = index
            used.add(index)
        slots = sorted(found.values())
        originals = {i: blocks[i] for i in slots}
        for slot, bullet in zip(slots, role.bullets, strict=False):
            source = originals[found[bullet.id]]
            blocks[slot] = replace(
                source, y=originals[slot].y, page=originals[slot].page, gap=originals[slot].gap,
                new_text=bullet.text if bullet.ai_changed else None,
            )  # fmt: skip
        for slot in slots[len(role.bullets) :]:
            blocks[slot] = replace(originals[slot], lines=[], new_text=None)
    if doc.summary:
        section = _section(blocks, body, r"summary|profile|objective|about")
        if not section:
            _unplaced("summary")
            return None
        blocks[section[0]].new_text = " ".join(s.text for s in doc.summary)
        for j in section[1:]:
            blocks[j] = replace(blocks[j], lines=[])
    if [s.name for s in doc.skills] != [s.name for s in base.skills]:
        section = _section(blocks, body, r"skill|technolog|tools|competenc|expertise")
        if section is None:
            _unplaced("skills")
            return None
        for j in section:
            text = reorder_skills(blocks[j].text, base, doc)
            if text is not None:
                blocks[j].new_text = text
    return [b for b in blocks if b.lines or b.rule]


def _unplaced(change: str) -> None:
    """Log which kind of change couldn't be placed in the original layout (never its text)."""
    logger.info("resume_layout_fallback", extra={"change": change})


def reorder_skills(text: str, base: ResumeDocument, doc: ResumeDocument) -> str | None:
    label, sep, rest = text.partition(":")
    if not sep or len(label) > 40:
        label, sep, rest = "", "", text
    items = [i.strip() for i in rest.split(",") if i.strip()]
    rank = {norm(s.name): n for n, s in enumerate(doc.skills)}
    removed = {norm(s.name) for s in base.skills} - set(rank)
    kept = [i for i in items if norm(i) not in removed]
    ranked = sorted((i for i in kept if norm(i) in rank), key=lambda i: rank[norm(i)])
    it = iter(ranked)
    ordered = [next(it) if norm(i) in rank else i for i in kept]
    if ordered == items:
        return None
    body = ", ".join(ordered)
    return f"{label}{sep} {body}" if sep else body


# --- drawing ------------------------------------------------------------------------------------


def _marks(lines: list[Line], base: Style) -> list[tuple[str, Style]]:
    """Phrases set in a style other than the paragraph's (bold keywords, italic names)."""
    marks: list[tuple[str, Style]] = []
    pieces = [p for line in lines for p in line.pieces]
    run: list[Piece] = []
    for piece in [*pieces, None]:
        if piece is not None and piece.style != base and (not run or piece.style == run[0].style):
            run.append(piece)
            continue
        if run:
            phrase = join_pieces(run).strip(" ,.;:")
            if len(phrase) >= 2:
                marks.append((phrase, run[0].style))
        run = [piece] if piece is not None and piece.style != base else []
    return marks


def _main_style(lines: list[Line]) -> Style:
    counts: dict[Style, int] = {}
    for line in lines:
        for p in line.pieces:
            counts[p.style] = counts.get(p.style, 0) + len(p.text)
    plain = {s: n for s, n in counts.items() if not s.bold} or counts
    return max(plain, key=lambda s: plain[s])


def _draw_line(canvas: Canvas, line: Line, shift: float, bullet_only: bool = False) -> None:
    y = line.baseline + shift
    if line.bullet is not None:
        b = line.bullet
        if b.text in ROUND_BULLETS:
            # Symbol-font bullets differ between fonts; a dot at the text's mid-height matches.
            d = min(0.36 * line.size, (b.x1 - b.x0) * 0.9)
            canvas.dot((b.x0 + b.x1) / 2, y - 0.28 * line.size, d, b.style.color)
        else:
            canvas.text(b.x0, y + b.dy, b.text, replace(b.style, size=line.size), fit=b.x1 - b.x0)
    if bullet_only:
        return
    for piece in line.pieces:
        canvas.text(piece.x0, y + piece.dy, piece.text, piece.style, fit=piece.x1 - piece.x0)


def render_like_original(layout: Layout, base: ResumeDocument, doc: ResumeDocument) -> bytes | None:
    blocks = plan(layout, base, doc)
    if blocks is None:
        return None
    right = _right_edges(layout)
    pitches = [
        b.lines[i + 1].baseline - b.lines[i].baseline
        for b in blocks_of(layout) for i in range(len(b.lines) - 1)
    ]  # fmt: skip
    pitch_default = sorted(pitches)[len(pitches) // 2] if pitches else 1.22 * _body_size(layout)
    full = [
        b.lines[i].x1 >= right[b.page] - 2
        for b in blocks_of(layout) for i in range(len(b.lines) - 1)
    ]  # fmt: skip
    justified = bool(full) and sum(full) / len(full) > 0.6
    bottom = max(line.baseline for line in layout.lines)
    limit = max(bottom, layout.height - 36)
    top = min(b.y for b in blocks)

    canvas = Canvas(layout.width, layout.height)
    links: dict[int, list[LayoutLink]] = {id(line): [] for line in layout.lines}
    for link in layout.links:
        for line in layout.lines:
            if line.page == link.page and link.top - 3 <= line.baseline <= link.bottom + 3:
                links[id(line)].append(link)
                break
    page = -1
    prev_last = 0.0  # output baseline of the previous block's last line
    for block in blocks:
        if block.page != page:
            canvas.pdf.add_page()
            page, y = block.page, block.y
        else:
            y = prev_last + (block.gap if block.gap is not None else 0.0)
        height = block.span
        if block.new_text is not None:
            lines_needed = len(wrap(canvas, [(block.new_text, _main_style(block.lines))],
                                    right[block.page] - block.lines[0].x0,
                                    _main_style(block.lines)))  # fmt: skip
            height = (lines_needed - 1) * _pitch(block, pitch_default)
        if y + height > limit:  # overflow: continue on a new page
            canvas.pdf.add_page()
            y = top
        prev_last = y + height
        if block.rule is not None:
            r = block.rule
            canvas.rule(r.x0, r.x1, y, r.width, r.color)
        elif block.new_text is not None:
            first = block.lines[0]
            style = _main_style(block.lines)
            if first.bullet is not None:
                _draw_line(canvas, first, y - first.baseline, bullet_only=True)
            multi = len(block.lines) > 1
            draw_paragraph(
                canvas, styled_runs(block.new_text, style, _marks(block.lines, style)),
                first.x0, right[block.page], y, _pitch(block, pitch_default), style,
                justify=(block.lines[0].x1 >= right[block.page] - 2) if multi else justified,
            )  # fmt: skip
        else:
            shift = y - block.lines[0].baseline
            for line in block.lines:
                _draw_line(canvas, line, shift)
                for link in links[id(line)]:
                    canvas.pdf.link(link.x0, link.top + shift, link.x1 - link.x0,
                                    link.bottom - link.top, link.uri)  # fmt: skip
    return canvas.output()


def _pitch(block: Block, default: float) -> float:
    if len(block.lines) > 1:
        return (block.lines[-1].baseline - block.lines[0].baseline) / (len(block.lines) - 1)
    return default


# --- classic template (no readable original layout) -------------------------------------------


def render_template_pdf(doc: ResumeDocument) -> bytes:
    """A one-column resume in the classic LaTeX style: ruled headings, dates on the right."""
    width, height, margin = 595.28, 841.89, 40.0  # A4
    canvas = Canvas(width, height)
    canvas.pdf.add_page()
    body = Style("serif", False, False, False, 9.5)
    bold, italic = replace(body, bold=True), replace(body, italic=True)
    pitch = 11.6
    y = margin + 10
    right = width - margin

    def need(space: float) -> None:
        nonlocal y
        if y + space > height - margin:
            canvas.pdf.add_page()
            y = margin + 10

    def centered(text: str, style: Style) -> None:
        canvas.text((width - canvas.width(text, style)) / 2, y, text, style)

    def two_sides(left: str, right_text: str, style: Style) -> None:
        canvas.text(margin, y, left, style)
        if right_text:
            canvas.text(right - canvas.width(right_text, style), y, right_text, style)

    def heading(title: str) -> None:
        nonlocal y
        need(40)
        y += 16
        canvas.text(margin, y, title, Style("serif", True, False, False, 10.5))
        canvas.rule(margin, right, y + 3.5, 0.4, BLACK)
        y += 15

    def paragraph(text: str, x0: float = margin, style: Style = body) -> None:
        nonlocal y
        need(pitch * 2)
        y = draw_paragraph(canvas, [(text, style)], x0, right, y, pitch, style, True) + pitch

    def bullet(text: str) -> None:
        nonlocal y
        need(pitch * 2)
        canvas.dot(margin + 5, y - 0.28 * body.size, 0.36 * body.size, BLACK)
        y = draw_paragraph(canvas, [(text, body)], margin + 12, right, y, pitch, body, True) + pitch

    c = doc.contact
    if c.name:
        centered(c.name, Style("serif", False, False, True, 18))
        y += 16
    contact = "  |  ".join(x for x in [c.phone, c.email, c.location, *c.links] if x)
    if contact:
        centered(contact, body)
        y += 4
    if doc.summary:
        heading("Summary")
        paragraph(" ".join(s.text for s in doc.summary))
    if doc.skills:
        heading("Skills")
        paragraph(", ".join(s.name for s in doc.skills))
    if doc.experience:
        heading("Experience")
        for role in doc.experience:
            need(pitch * 3)
            two_sides(role.title, role.date_text or "", bold)
            y += pitch
            two_sides(role.company, role.location or "", italic)
            y += pitch
            for b in role.bullets:
                bullet(b.text)
            y += 3
    if doc.projects:
        heading("Projects")
        for p in doc.projects:
            need(pitch * 2)
            tech = ", ".join(p.technologies)
            canvas.text(margin, y, p.name, bold)
            if tech:
                canvas.text(margin + canvas.width(p.name + "  ", bold), y, f"— {tech}", italic)
            y += pitch
            if p.description:
                bullet(p.description)
    if doc.education:
        heading("Education")
        for e in doc.education:
            need(pitch * 2)
            two_sides(education_line(e.model_copy(update={"date_text": None})), e.date_text or "",
                      body)  # fmt: skip
            y += pitch
    if doc.certifications:
        heading("Certifications")
        for cert in doc.certifications:
            bullet(cert.name + (f" ({cert.issuer})" if cert.issuer else ""))
    return canvas.output()


def render_pdf(
    layout: Layout | None, base: ResumeDocument, doc: ResumeDocument
) -> tuple[bytes, bool]:
    """The PDF and whether it kept the original's format."""
    if layout is not None:
        rendered = render_like_original(layout, base, doc)
        if rendered is not None:
            return rendered, True
    return render_template_pdf(doc), False
