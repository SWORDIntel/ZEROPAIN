"""Backward-compatible import path for dissociation research verification."""

from zeropain.verification import (  # noqa: F401
    CheckBit,
    CheckResult,
    VerificationRecord,
    append_record,
    digest,
    enabled,
    finite_check,
    independent_check,
    probability_range_check,
    relation_check,
    relation_count_not_exceed_total,
    relation_sum_close,
    replay_check,
    strict_enabled,
    verify,
)

__all__ = [
    "CheckBit",
    "CheckResult",
    "VerificationRecord",
    "append_record",
    "digest",
    "enabled",
    "finite_check",
    "independent_check",
    "probability_range_check",
    "relation_check",
    "relation_count_not_exceed_total",
    "relation_sum_close",
    "replay_check",
    "strict_enabled",
    "verify",
]
