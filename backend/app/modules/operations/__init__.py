"""operations module: counselor back-office workflows (no owned tables).

Aggregates cross-module operations (account/staff management, academic
corrections, audit views) behind Counselor authorization. Reads/writes go
through the owning modules' services per ARCHITECTURE.md.
"""
