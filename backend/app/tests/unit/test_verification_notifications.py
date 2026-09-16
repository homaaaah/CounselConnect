"""Decision notification outcomes remain visible after an irreversible decision."""

from types import SimpleNamespace

from app.modules.enrollment_verification import service as module
from app.modules.enrollment_verification.service import EnrollmentVerificationService


def notifier():
    return object.__new__(EnrollmentVerificationService)


def inputs():
    return SimpleNamespace(verification_id=17, valid_until="2027-09-16"), SimpleNamespace(email="student@example.edu")


def test_notification_reports_smtp_acceptance(monkeypatch):
    verification, student = inputs()
    monkeypatch.setattr(module, "smtp_configured", lambda: True)
    monkeypatch.setattr(module, "send_email", lambda **_: True)
    assert notifier()._notify(verification, student, approved=True) == "SENT"


def test_notification_reports_missing_smtp_configuration(monkeypatch):
    verification, student = inputs()
    monkeypatch.setattr(module, "smtp_configured", lambda: False)
    assert notifier()._notify(verification, student, approved=True) == "NOT_CONFIGURED"


def test_notification_reports_smtp_failure_without_rethrowing(monkeypatch):
    verification, student = inputs()
    monkeypatch.setattr(module, "smtp_configured", lambda: True)

    def fail(**_):
        raise OSError("synthetic SMTP failure")

    monkeypatch.setattr(module, "send_email", fail)
    assert notifier()._notify(verification, student, approved=False, comment="Reviewed") == "FAILED"
