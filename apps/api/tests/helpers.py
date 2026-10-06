"""Builders for test documents. All content is fictional."""

import io
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / "resumes" / name).read_text()


def ai_fixture(name: str) -> str:
    """A recorded LLM response (JSON text) for the resume fixture of the same name."""
    return json.dumps(json.loads((FIXTURES / "ai" / "resume_extraction" / name).read_text()))


def _pdf_escape(line: str) -> str:
    # Standard Type1 fonts only cover latin-1; bullets and dashes become "-".
    line = "".join(ch if ord(ch) < 256 else "-" for ch in line)
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(lines: list[str], pages: int = 1) -> bytes:
    """A minimal, valid text PDF (Helvetica, one text object per page)."""
    per_page = max(1, -(-len(lines) // pages))
    chunks = [lines[i * per_page : (i + 1) * per_page] for i in range(pages)]
    objects: list[bytes] = []
    page_ids = [4 + i * 2 for i in range(pages)]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, chunk in enumerate(chunks):
        content_id = page_ids[i] + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        ops = ["BT", "/F1 10 Tf", "14 TL", "40 760 Td"]
        for line in chunk:
            ops.append(f"({_pdf_escape(line)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


def make_docx(lines: list[str]) -> bytes:
    import docx

    document = docx.Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


HEADINGS = {"Summary", "Skills", "Experience", "Projects", "Education", "Certifications"}


def make_styled_pdf(text: str, bold: tuple[str, ...] = ()) -> bytes:
    """A LaTeX-style resume PDF (Latin Modern, ruled headings, bold phrases inside bullets)."""
    import re

    from fpdf import FPDF

    from app.services.tailoring.pdf_render import FONT_DIR

    pdf = FPDF(unit="pt", format="letter")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    for name in ("lmroman9-regular", "lmroman9-bold", "lmroman10-bold", "lmromancaps10-regular"):
        pdf.add_font(name, "", str(FONT_DIR / f"{name}.otf"))
    y = 30.0
    pattern = re.compile("(" + "|".join(map(re.escape, bold)) + ")") if bold else None
    for n, line in enumerate(text.strip().splitlines()):
        if not line.strip():
            y += 4
            continue
        if n == 0:
            pdf.set_font("lmromancaps10-regular", size=17)
            pdf.text((612 - pdf.get_string_width(line)) / 2, y, line)
            y += 14
        elif n < 3:
            pdf.set_font("lmroman9-regular", size=9)
            pdf.text((612 - pdf.get_string_width(line)) / 2, y, line)
            y += 11
        elif line in HEADINGS:
            y += 8
            pdf.set_font("lmroman10-bold", size=10)
            pdf.text(29, y, line)
            pdf.set_line_width(0.4)
            pdf.line(29, y + 3, 583, y + 3)
            y += 16
        else:
            x = 29.0
            if line.startswith("• "):
                pdf.set_font("lmroman9-regular", size=9)
                pdf.text(31, y, "•")
                line, x = line[2:], 40.0
            for part in pattern.split(line) if pattern else [line]:
                pdf.set_font("lmroman9-bold" if part in bold else "lmroman9-regular", size=9)
                pdf.text(x, y, part)
                x += pdf.get_string_width(part)
            y += 11
    return bytes(pdf.output())
