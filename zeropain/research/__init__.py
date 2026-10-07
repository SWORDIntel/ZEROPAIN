"""Research-only utilities and hypothesis tooling for ZeroPain."""

from .legacy_claims import (
    LegacyClaimFinding,
    audit_claim_text,
    audit_legacy_activity_file,
    audit_records,
    parse_legacy_activity_file,
    write_json_report,
)

__all__ = [
    "LegacyClaimFinding",
    "audit_claim_text",
    "audit_legacy_activity_file",
    "audit_records",
    "parse_legacy_activity_file",
    "write_json_report",
]
