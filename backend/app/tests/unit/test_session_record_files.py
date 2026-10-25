"""Session-document validation runs without a database."""

import io

import pytest
from PIL import Image

from app.core.exceptions import AppError
from app.modules.appointments.service import AppointmentsService


def service():
    return AppointmentsService(None)


def pdf_bytes():
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "blue").save(buffer, format="PNG")
    return buffer.getvalue()


def error_code(fn):
    with pytest.raises(AppError) as exc:
        fn()
    return exc.value.code


def test_accepts_pdf_and_png():
    mime, ext = service()._validate_session_file(pdf_bytes(), "referral.pdf")
    assert (mime, ext) == ("application/pdf", "pdf")
    mime, ext = service()._validate_session_file(png_bytes(), "scan.PNG")
    assert (mime, ext) == ("image/png", "png")


def test_rejects_wrong_type_fake_content_and_oversize():
    assert error_code(lambda: service()._validate_session_file(b"hello", "notes.txt")) == "SESSION_FILE_TYPE_INVALID"
    assert error_code(lambda: service()._validate_session_file(b"not a pdf", "fake.pdf")) == "SESSION_FILE_INVALID"
    assert error_code(lambda: service()._validate_session_file(b"\xff\xd8\xffbroken", "photo.jpg")) == "SESSION_FILE_INVALID"

    oversized = pdf_bytes() + b" " * (10 * 1024 * 1024)
    assert error_code(lambda: service()._validate_session_file(oversized, "big.pdf")) == "SESSION_FILE_TOO_LARGE"
