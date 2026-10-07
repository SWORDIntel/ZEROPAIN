#!/usr/bin/env python3
"""Audit ZeroPain's generated legacy opioid activity corpus.

This command does not validate pharmacology. It extracts legacy claims, assigns
review flags, and emits a machine-readable queue for literature verification.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from zeropain.research.legacy_claims import audit_legacy_activity_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="parsed_activities.py",
        help="Path to the generated legacy activity corpus.",
    )
    parser.add_argument(
        "--output",
        default="runs/legacy_opioid_claim_audit.json",
        help="JSON report destination.",
    )
    parser.add_argument(
        "--only-flagged",
        action="store_true",
        help="Exclude claims for which no prioritization rule fired.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    findings = audit_legacy_activity_file(args.source)
    if args.only_flagged:
        findings = [finding for finding in findings if finding.flags]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    flag_counts = Counter(flag for finding in findings for flag in finding.flags)
    payload = {
        "schema_version": 1,
        "source": str(args.source),
        "warning": (
            "Legacy historical claims only. No entry is eligible for validated "
            "simulation until independently reviewed against current literature."
        ),
        "finding_count": len(findings),
        "flag_counts": dict(sorted(flag_counts.items())),
        "findings": [finding.to_dict() for finding in findings],
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {len(findings)} legacy claims to {output}")
    for flag, count in sorted(flag_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{count:4d}  {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
