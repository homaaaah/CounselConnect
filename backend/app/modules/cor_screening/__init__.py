"""cor_screening module: automated COR (registration form) verification.

ADR-029 replaces the human review queue. A student submits email + password +
current COR; the PDF is screened (format match, OCR extraction, embedded
barcode) and the Student confirms the extracted fields, which activates the
account. COR bytes are never stored in MySQL — only temporary private-storage
metadata in `cor_screening_files`, deleted after confirmation/resubmission or
the seven-day TTL. Raw OCR text and raw barcode payloads are never persisted.
"""
