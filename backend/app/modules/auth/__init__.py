"""auth module: login/session/CSRF (ADR-019).

Opaque MySQL-backed sessions in a secure HttpOnly cookie with a
session-bound CSRF token; Argon2id passwords with transparent bcrypt
upgrade; 1h idle / 12h absolute limits.
"""
