"""Headless installed Chrome, real Vite UI and disposable FastAPI/MySQL.

Document extraction is stubbed by committed_correction; no application data,
real COR, external network or physical mobile device is used.
"""

import base64
import hashlib
import os

import pytest
from sqlalchemy.orm import Session

from app.modules.cor_screening.models import CorScreeningFile
from app.modules.profile_change.models import ProfileChangeRequest
from .test_correction_decision_concurrency import committed_correction  # noqa: F401
from .test_management_frontend import run_management_workflows


@pytest.mark.parametrize("viewport", ["desktop", "mobile"])
@pytest.mark.skipif(os.environ.get("COUNSELCONNECT_BROWSER_REHEARSAL") != "1",
                    reason="Opt-in: requires installed Playwright and Chrome")
def test_management_browser(mysql_test_engine, committed_correction, tmp_path, viewport):
    run_management_workflows(mysql_test_engine, committed_correction,
        script="browser-management.cjs", extra_env={
            "COUNSELCONNECT_TEST_VIEWPORT": viewport,
            "COUNSELCONNECT_TEST_ARTIFACTS": str(tmp_path),
        })


@pytest.mark.skipif(os.environ.get("COUNSELCONNECT_BROWSER_REHEARSAL") != "1",
                    reason="Opt-in: requires installed Playwright and Chrome")
def test_management_browser_conflict_and_revocation(mysql_test_engine, committed_correction, tmp_path):
    # A valid, locally generated one-page PDF enables browser PDF smoke checks;
    # it is synthetic display evidence, not a real COR or OCR accuracy fixture.
    stream = b"BT /F1 18 Tf 50 740 Td (Synthetic COR browser rehearsal) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    pdf, offsets = b"%PDF-1.4\n", [0]
    for index, item in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\n".encode() + item + b"\nendobj\n"
    start = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    pdf += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    pdf += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    data = committed_correction
    data["path"].write_bytes(pdf)
    with Session(mysql_test_engine) as db:
        row = db.get(ProfileChangeRequest, data["request"])
        file = db.get(CorScreeningFile, row.evidence_file_id)
        file.sha256_hash = row.evidence_sha256_hash = hashlib.sha256(pdf).digest()
        file.size_bytes = len(pdf)
        db.commit()
    run_management_workflows(mysql_test_engine, data, script="browser-management.cjs", extra_env={
        "COUNSELCONNECT_TEST_VIEWPORT": "desktop",
        "COUNSELCONNECT_TEST_ARTIFACTS": str(tmp_path),
        "COUNSELCONNECT_TEST_EXTENDED": "1",
        "COUNSELCONNECT_TEST_PDF_BASE64": base64.b64encode(pdf).decode(),
    })
