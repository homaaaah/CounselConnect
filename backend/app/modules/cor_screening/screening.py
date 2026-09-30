"""Automated COR screening engine (pure functions; no database, no HTTP).

Ported from the approved RegistrationWithMachineLearning prototype and
hardened for this repository:

- Uses only configured external binaries (`pdftotext`, `pdftoppm`,
  `tesseract`) plus `zxing-cpp`/`Pillow`. Raw OCR text and raw barcode
  payloads are NEVER logged or persisted — callers may only store codes,
  scores, and a SHA-256 digest of the payload.
- No campus/program auto-creation: unmatched names are returned to the
  caller so the confirming Student can select from existing reference data.
- A missing/failed document-processing dependency raises
  `ScreeningUnavailableError` so callers fail closed (never auto-activate).
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Internal (pre-persistence) barcode outcomes.
BARCODE_NOT_PROCESSED = "NOT_PROCESSED"
BARCODE_NOT_FOUND = "NOT_FOUND"
BARCODE_UNREADABLE = "UNREADABLE"
BARCODE_INVALID_FORMAT = "INVALID_FORMAT"
BARCODE_DECODED = "DECODED"
BARCODE_MISMATCH = "MISMATCH"

STUDENT_NO_RE = re.compile(r"^\d{8}-[A-Za-z]$")
ACADEMIC_PERIOD_RE = re.compile(r"\b(\d{4}\s*-\s*\d{4})\b")
VALIDITY_DATE_RE = re.compile(
    r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})\b"
)
_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y",
    "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y",
)

# Weighted format markers (sum 100 -> normalized to 0..1).
MARKERS = [
    (r"university of caloocan city", 25),
    (r"registration\s+form", 10),
    (r"student\s*#|student\s*number", 15),
    (r"name\s*:", 10),
    (r"course\s*/\s*year\s*/\s*section", 15),
    (r"campus\s*:", 10),
    (r"school\s+year\s*:", 5),
    (r"\bsubject\b.{0,40}\bunit\b", 10),
]
REQUIRED = ("student_no", "name", "course", "year", "section")

STUDENT_NO_LABELS = ["student #", "student number", "student no", "student id", "id number", "id no"]
NAME_LABELS = ["name", "full name", "student name", "complete name", "name of student"]
COURSE_LABELS = ["course", "program", "degree program", "degree", "curriculum"]
YEAR_LABELS = ["year level", "year", "grade level", "level"]
SECTION_LABELS = ["section", "class section", "block"]
CYS_LABELS = ["course/year/section", "course / year / section", "course-year-section"]
CAMPUS_LABELS = ["campus", "branch", "site"]
PERIOD_LABELS = ["school year", "academic year", "academic period"]
VALIDITY_LABELS = [
    "valid until", "valid thru", "valid through", "valid date", "validity",
    "valid up to", "expires", "expiry", "expiration",
]
LABEL_WORDS = ["student", "name", "course", "section", "semester", "scheme", "date",
               "campus", "program", "block", "school year"]

FAILURE_TEXT = {
    "LOW_FORMAT_SCORE": "The document did not match the expected COR format.",
    "LOW_EXTRACTION_CONFIDENCE": "Some required details could not be read clearly.",
    "MISSING_REQUIRED_FIELDS": "Required details are missing from the document.",
    "UNREADABLE_DOCUMENT": "No readable text was found in the document.",
    "TECHNICAL_ERROR": "A technical problem occurred while processing the document.",
    "BARCODE_NOT_FOUND": "No barcode was found on the document.",
    "BARCODE_UNREADABLE": "The barcode on the document could not be read.",
    "BARCODE_INVALID_FORMAT": "The barcode payload format is not valid.",
    "BARCODE_MISMATCH": "The barcode does not match the extracted student number.",
    "REJECTED_BY_STUDENT": "The extracted details were rejected.",
    "FIELD_MAPPING_FAILED": "The document details could not be matched to school records.",
}


class ScreeningUnavailableError(RuntimeError):
    """A required document-processing dependency is missing or unusable."""


@dataclass
class ExtractedFields:
    student_no: str = ""
    name: str = ""
    course: str = ""
    year: str = ""
    section: str = ""
    campus: str = ""
    academic_period: str = ""
    valid_until: str = ""  # ISO date string when readable


@dataclass
class ScreeningResult:
    fields: ExtractedFields
    method: str
    format_score: float
    extraction_confidence: float
    missing: list[str] = field(default_factory=list)
    barcode_status: str = BARCODE_NOT_PROCESSED
    barcode_symbology: str | None = None
    # In-memory only. Callers must hash it, never persist or log it verbatim.
    barcode_payload: str | None = None
    barcode_format_valid: bool | None = None
    barcode_student_number_match: bool | None = None
    barcode_academic_period_match: bool | None = None
    # Decode certainty: 1.0 when a valid barcode symbol was decoded, else None.
    barcode_decode_confidence: float | None = None

    @property
    def barcode_matched(self) -> bool:
        return self.barcode_status == BARCODE_DECODED


def _resolve_binary(path: str) -> str | None:
    if not path:
        return None
    if os.path.isabs(path):
        return path if os.path.exists(path) else None
    return shutil.which(path)


def ensure_dependencies(settings) -> None:
    """Raise ScreeningUnavailableError unless every binary/tool is usable."""
    missing = []
    for name, path in (
        ("pdftotext", settings.pdftotext_path),
        ("pdftoppm", settings.pdftoppm_path),
        ("tesseract", settings.tesseract_path),
    ):
        if _resolve_binary(path) is None:
            missing.append(name)
    try:
        import zxingcpp  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception:  # noqa: BLE001 - any import/ABI failure means unavailable
        missing.append("zxing-cpp/Pillow")
    if missing:
        raise ScreeningUnavailableError(
            "COR screening dependencies unavailable: " + ", ".join(missing)
        )


# ------------------------------------------------------------------ extraction


def first_col(value: str) -> str:
    return re.split(r"\s{3,}", value.strip())[0].strip()


def looks_label(value: str) -> bool:
    value = value.strip()
    if not value:
        return True
    if re.search(r":\s*$", value) and len(value.split()) <= 6:
        return True
    low = value.lower()
    return any(
        re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low) for w in LABEL_WORDS
    )


def labeled_value(text: str, labels: list[str]) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for lab in labels:
            m = re.search(r"(?<![A-Za-z0-9])" + re.escape(lab) + r"(?![A-Za-z0-9])(.*)$", line, re.I)
            if not m:
                continue
            val = first_col(re.sub(r"^\s*[#:\-]*\s*", "", m.group(1)))
            if val and not looks_label(val):
                return val
            for nxt in lines[i + 1:]:
                cand = first_col(nxt.strip())
                if cand and not looks_label(cand):
                    return cand
    return ""


def inline_value(text: str, labels: list[str]) -> str:
    for line in text.splitlines():
        for lab in labels:
            m = re.search(
                r"(?<![A-Za-z0-9])" + re.escape(lab) + r"(?![A-Za-z0-9])\s*[#:\-]?\s*(.*)$",
                line,
                re.I,
            )
            if m:
                val = first_col(m.group(1).strip())
                if val:
                    return val
    return ""


def column_value(text: str, labels: list[str]) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for lab in labels:
            m = re.search(r"(?<![A-Za-z0-9])" + re.escape(lab) + r"(?![A-Za-z0-9])", line, re.I)
            if not m:
                continue
            off = m.start()
            for nxt in lines[i:]:
                if not nxt.strip():
                    continue
                seg = nxt[off:] if off < len(nxt) else nxt
                hit = ACADEMIC_PERIOD_RE.search(seg)
                if hit:
                    return hit.group(0)
    return ""


def normalize_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z\s'\-,.]", " ", value or "")
    return re.sub(r"\s+", " ", value).strip().title()


def normalize_year(value: str) -> str:
    value = (value or "").strip()
    m = re.search(r"\b([1-9]|10)\b", value)
    if m:
        return m.group(1)
    words = {"first": "1", "second": "2", "third": "3", "fourth": "4",
             "fifth": "5", "sixth": "6", "seventh": "7", "eighth": "8"}
    m = re.search(r"(first|second|third|fourth|fifth|sixth|seventh|eighth)", value, re.I)
    return words[m.group(1).lower()] if m else value


def parse_date(value: str) -> str | None:
    """Return an ISO date string from free text, or None if not parseable."""
    if not value:
        return None
    m = VALIDITY_DATE_RE.search(value)
    if not m:
        return None
    raw = re.sub(r"\s+", " ", m.group(1).replace(",", " ")).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def split_name(full: str) -> tuple[str, str | None, str]:
    """Return (first, middle, last) from a COR name string."""
    full = (full or "").strip()
    if not full:
        return "", None, ""
    if "," in full:
        last, rest = full.split(",", 1)
        parts = rest.strip().split()
        return (parts[0] if parts else ""), (" ".join(parts[1:]) or None), last.strip()
    parts = full.split()
    if len(parts) == 1:
        return parts[0], None, ""
    return parts[0], (" ".join(parts[1:-1]) or None), parts[-1]


def parse_fields(text: str) -> ExtractedFields:
    fields = ExtractedFields()
    if not text.strip():
        return fields

    raw = labeled_value(text, STUDENT_NO_LABELS)
    m = re.search(r"([A-Z0-9][A-Z0-9\-]{4,})", raw, re.I) if raw else None
    if m:
        fields.student_no = m.group(1).upper()

    fields.name = normalize_name(labeled_value(text, NAME_LABELS))
    fields.campus = inline_value(text, CAMPUS_LABELS)
    fields.academic_period = column_value(text, PERIOD_LABELS)

    cys = labeled_value(text, CYS_LABELS)
    if cys:
        m = re.match(
            r"^\s*([A-Za-z][A-Za-z\s]*?)\s+(\d+)(?:st|nd|rd|th)?\s*[-\s]\s*(.+?)\s*$", cys, re.I
        )
        if m:
            fields.course = m.group(1).strip().upper()
            fields.year = m.group(2)
            fields.section = m.group(3).strip().upper()
        else:
            fields.course = cys

    if not fields.course:
        fields.course = (labeled_value(text, COURSE_LABELS) or "").strip()
    if not fields.year:
        fields.year = normalize_year(labeled_value(text, YEAR_LABELS))
    if not fields.section:
        fields.section = (labeled_value(text, SECTION_LABELS) or "").strip()
    fields.valid_until = parse_date(labeled_value(text, VALIDITY_LABELS) or "") or ""
    return fields


# ------------------------------------------------------------------ documents


def _run(argv: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, timeout=timeout)


def _private_temp_dir(settings) -> str:
    """Scratch directory INSIDE the private COR store.

    Intermediate OCR text and rasterized pages must never land in the shared
    OS temp directory; keeping them under the private store preserves the
    'no raw OCR text outside private storage' boundary.
    """
    base = os.path.join(settings.cor_storage_root, "tmp")
    os.makedirs(base, exist_ok=True)
    return base


def pdf_text(path: str, settings) -> str:
    binary = _resolve_binary(settings.pdftotext_path)
    if binary is None:
        raise ScreeningUnavailableError("pdftotext unavailable")
    out = os.path.join(_private_temp_dir(settings), f"cor_{os.urandom(6).hex()}.txt")
    try:
        _run([binary, "-layout", "-enc", "UTF-8", path, out], timeout=60)
        if os.path.exists(out):
            with open(out, encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        return ""
    except (subprocess.SubprocessError, OSError):
        return ""
    finally:
        if os.path.exists(out):
            os.remove(out)


def render_pages(path: str, settings) -> list[str]:
    binary = _resolve_binary(settings.pdftoppm_path)
    if binary is None:
        raise ScreeningUnavailableError("pdftoppm unavailable")
    prefix = os.path.join(_private_temp_dir(settings), f"cor_{os.urandom(6).hex()}")
    try:
        _run([binary, "-png", "-r", "300", "-f", "1", "-l", "3", path, prefix], timeout=180)
        return sorted(glob.glob(prefix + "*.png"))
    except (subprocess.SubprocessError, OSError):
        return []


def ocr_text(pdf_path_: str, settings) -> str:
    binary = _resolve_binary(settings.tesseract_path)
    if binary is None:
        raise ScreeningUnavailableError("tesseract unavailable")
    images = render_pages(pdf_path_, settings)
    if not images:
        return ""
    try:
        result = _run([binary, images[0], "stdout"], timeout=180)
        return result.stdout.decode("utf-8", "ignore")
    except (subprocess.SubprocessError, OSError):
        return ""
    finally:
        for image in images:
            try:
                os.remove(image)
            except OSError:
                pass


def screen_barcode(pdf_path_: str, fields: ExtractedFields, settings) -> tuple[str, str | None, str | None]:
    """Return (status, symbology, payload). Payload is in-memory only."""
    try:
        import zxingcpp
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        raise ScreeningUnavailableError("zxing-cpp/Pillow unavailable") from exc

    images = render_pages(pdf_path_, settings)
    if not images:
        return BARCODE_UNREADABLE, None, None
    try:
        student_no = fields.student_no
        normalize = lambda v: re.sub(r"[^A-Za-z0-9]", "", v).upper()  # noqa: E731
        for img in images:
            with Image.open(img) as image:
                codes = zxingcpp.read_barcodes(image)
            found = [c for c in codes if c.text and str(c.text).strip()]
            if not found:
                continue
            payload = str(found[0].text)
            symbology = str(found[0].format)
            matched = bool(student_no) and normalize(payload) == normalize(student_no)
            return (BARCODE_DECODED if matched else BARCODE_MISMATCH), symbology, payload
        return BARCODE_NOT_FOUND, None, None
    except Exception:  # noqa: BLE001 - decoder failure is not fatal
        return BARCODE_NOT_PROCESSED, None, None
    finally:
        for image in images:
            try:
                os.remove(image)
            except OSError:
                pass


def screen_pdf(pdf_path: str, settings) -> ScreeningResult:
    """Screen one COR PDF. Raises ScreeningUnavailableError if tools are missing."""
    ensure_dependencies(settings)

    text = pdf_text(pdf_path, settings)
    method = "text"
    if len(text.strip()) < 40:
        ocr = ocr_text(pdf_path, settings)
        if len(ocr.strip()) > len(text.strip()):
            text, method = ocr, "ocr"
    if len(text.strip()) < 40:
        method = "none"

    fields = parse_fields(text)
    missing = [name for name in REQUIRED if not str(getattr(fields, name)).strip()]
    format_score = round(sum(w for pat, w in MARKERS if re.search(pat, text, re.I)) / 100, 4)
    extraction_confidence = round((len(REQUIRED) - len(missing)) / len(REQUIRED), 4)

    barcode_status, symbology, payload = screen_barcode(pdf_path, fields, settings)
    format_valid = bool(payload) and bool(STUDENT_NO_RE.match(payload.strip()))
    student_match = None
    period_match = None
    if payload is not None:
        normalize = lambda v: re.sub(r"[^A-Za-z0-9]", "", v).upper()  # noqa: E731
        student_match = bool(fields.student_no) and normalize(payload) == normalize(fields.student_no)
        # Cross-check any academic period encoded in the payload against OCR.
        payload_period = ACADEMIC_PERIOD_RE.search(payload)
        if payload_period and fields.academic_period:
            digits = lambda v: re.sub(r"[^0-9]", "", v)  # noqa: E731
            period_match = digits(payload_period.group(1)) == digits(fields.academic_period)
            if not period_match:
                barcode_status = BARCODE_MISMATCH
    decode_confidence = 1.0 if barcode_status in (BARCODE_DECODED, BARCODE_MISMATCH) else None

    return ScreeningResult(
        fields=fields,
        method=method,
        format_score=format_score,
        extraction_confidence=extraction_confidence,
        missing=missing,
        barcode_status=barcode_status,
        barcode_symbology=symbology,
        barcode_payload=payload,
        barcode_format_valid=format_valid,
        barcode_student_number_match=student_match,
        barcode_academic_period_match=period_match,
        barcode_decode_confidence=decode_confidence,
    )


def derive_outcome(result: ScreeningResult, settings) -> tuple[str, str | None]:
    """Return (screening status, failure_reason_code)."""
    if result.method == "none":
        return "NEEDS_RESUBMISSION", "UNREADABLE_DOCUMENT"

    if result.barcode_status != BARCODE_DECODED:
        if result.barcode_status in (BARCODE_NOT_FOUND, BARCODE_UNREADABLE,
                                     BARCODE_INVALID_FORMAT, BARCODE_MISMATCH):
            return "NEEDS_RESUBMISSION", "BARCODE_" + result.barcode_status
        # Decoder/processing failure we cannot attribute to the document:
        # unrecoverable, so record FAILED (retry/support path).
        return "FAILED", "TECHNICAL_ERROR"

    # The Student cannot edit verified fields, so every required field must be
    # present before we can ask for confirmation.
    if result.format_score < settings.cor_format_pass_score:
        return "NEEDS_RESUBMISSION", "LOW_FORMAT_SCORE"
    if result.missing:
        return "NEEDS_RESUBMISSION", "MISSING_REQUIRED_FIELDS"
    if result.extraction_confidence < settings.cor_extraction_pass_score:
        return "NEEDS_RESUBMISSION", "LOW_EXTRACTION_CONFIDENCE"
    return "AWAITING_CONFIRMATION", None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
