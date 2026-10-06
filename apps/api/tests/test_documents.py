import io
import zipfile

import pytest

from app.core.config import get_settings
from app.services.resume.documents import (
    ExtractionError,
    UploadRejectedError,
    detect_file_type,
    extract_text,
    safe_display_name,
    validate_upload,
)
from tests.helpers import fixture_text, make_docx, make_pdf

RESUME_LINES = fixture_text("sneha_backend.txt").splitlines()


def test_detects_types_by_content() -> None:
    assert detect_file_type(make_pdf(["hello"])) == "pdf"
    assert detect_file_type(make_docx(["hello"])) == "docx"
    assert detect_file_type(b"plain text resume") == "txt"
    assert detect_file_type(b"MZ\x90\x00\x03\x00binary") is None
    plain_zip = io.BytesIO()
    with zipfile.ZipFile(plain_zip, "w") as zf:
        zf.writestr("readme.txt", "not a document")
    assert detect_file_type(plain_zip.getvalue()) is None


def test_validate_accepts_matching_types() -> None:
    settings = get_settings()
    assert validate_upload("cv.PDF", make_pdf(["x"]), settings) == "pdf"
    assert validate_upload("cv.docx", make_docx(["x"]), settings) == "docx"
    assert validate_upload("cv.txt", b"text", settings) == "txt"


@pytest.mark.parametrize(
    ("filename", "data", "message"),
    [
        ("cv.pdf", b"", "empty"),
        ("cv.exe", b"text", "PDF, DOCX or TXT"),
        ("cv.doc", b"text", "PDF, DOCX or TXT"),
        ("cv.pdf", b"MZ\x90\x00\x03\x00binary", "not a valid"),
        ("cv.pdf", b"just text renamed", "content is TXT"),
        ("cv.txt", b"%PDF-1.4 fake", "content is PDF"),
        (None, b"text", "PDF, DOCX or TXT"),
    ],
)
def test_validate_rejects(filename: str | None, data: bytes, message: str) -> None:
    with pytest.raises(UploadRejectedError, match=message):
        validate_upload(filename, data, get_settings())


def test_validate_rejects_oversize_and_zip_bombs() -> None:
    settings = get_settings().model_copy(
        update={"max_upload_bytes": 1000, "max_docx_uncompressed_bytes": 10_000}
    )
    with pytest.raises(UploadRejectedError, match="larger than"):
        validate_upload("cv.txt", b"x" * 1001, settings)
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "a" * 50_000)
    assert len(bomb.getvalue()) < 1000
    with pytest.raises(UploadRejectedError, match="uncompressed"):
        validate_upload("cv.docx", bomb.getvalue(), settings)


def test_extract_pdf_docx_txt() -> None:
    settings = get_settings()
    pdf = extract_text(make_pdf(RESUME_LINES, pages=2), "pdf", settings)
    assert pdf.page_count == 2
    assert "Acme Analytics Pvt Ltd" in pdf.text
    docx_doc = extract_text(make_docx(RESUME_LINES), "docx", settings)
    assert "RV College of Engineering" in docx_doc.text
    txt = extract_text("\n".join(RESUME_LINES).encode(), "txt", settings)
    assert txt.text.startswith("Sneha Rao")


def test_extract_limits() -> None:
    settings = get_settings().model_copy(update={"max_resume_pages": 2, "max_resume_chars": 500})
    with pytest.raises(ExtractionError, match="3 pages"):
        extract_text(make_pdf(RESUME_LINES, pages=3), "pdf", settings)
    with pytest.raises(ExtractionError, match="too long"):
        extract_text(("word " * 200).encode(), "txt", settings)
    with pytest.raises(ExtractionError, match="scanned image"):
        extract_text(make_pdf([]), "pdf", settings)
    with pytest.raises(ExtractionError, match="could not be read"):
        extract_text(b"%PDF-1.4 garbage that is not a pdf", "pdf", settings)
    with pytest.raises(ExtractionError, match="UTF-8"):
        extract_text(b"\xff\xfe" + "x".encode("utf-16-le") * 100, "txt", settings)


def test_safe_display_name() -> None:
    assert safe_display_name("../../etc/passwd") == "passwd"
    assert safe_display_name("C:\\Users\\me\\My CV.pdf") == "My CV.pdf"
    assert safe_display_name('<script>"x".pdf') == "scriptx.pdf"
    assert safe_display_name(None) == "resume"
