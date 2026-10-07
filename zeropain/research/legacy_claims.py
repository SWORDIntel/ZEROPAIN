"""Research-only audit utilities for ZeroPain's legacy opioid corpus.

The legacy corpus contains historical, informal pharmacology notes. It is useful
for hypothesis generation, but claims must not silently become simulation facts.

This module performs claim triage, not pharmacological validation.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class LegacyClaimFinding:
    compound: str
    claim: str
    flags: tuple[str, ...]
    evidence_status: str = "legacy_unverified"
    simulation_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "absolute_safety_or_dependence_claim",
        re.compile(
            r"\b(?:does not|doesn't|no|non)[ -]?(?:produce )?"
            r"(?:addiction|dependence|dependency|tolerance)\b",
            re.IGNORECASE,
        ),
    ),
    ("cure_claim", re.compile(r"\b(?:cure|cures|curative)\b", re.IGNORECASE)),
    (
        "high_or_ultrapotent_claim",
        re.compile(
            r"\b(?:\d{2,}(?:,\d{3})*x|ultra[- ]?potent|super[- ]?potent)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "legal_or_schedule_status_may_be_stale",
        re.compile(r"\b(?:legal|unscheduled|uncontrolled|rc\b)", re.IGNORECASE),
    ),
    (
        "misuse_sensitive_potentiation_claim",
        re.compile(
            r"\b(?:potentiat(?:e|es|ed|ion)|bioavailability|faster onset)\b",
            re.IGNORECASE,
        ),
    ),
    ("nmda_activity", re.compile(r"\bNMDA\b", re.IGNORECASE)),
    ("kappa_activity", re.compile(r"(?:\bKOR\b|\bkappa\b|κ)", re.IGNORECASE)),
    (
        "nop_or_orl1_activity",
        re.compile(r"(?:\bNOP\b|\bORL[- ]?1\b|nociceptin)", re.IGNORECASE),
    ),
    ("delta_activity", re.compile(r"(?:\bDOR\b|\bdelta\b|δ)", re.IGNORECASE)),
    (
        "biased_signaling_claim",
        re.compile(
            r"(?:beta[- ]?arrestin|β[- ]?arrestin|G[- ]?protein bias)",
            re.IGNORECASE,
        ),
    ),
    (
        "respiratory_claim",
        re.compile(r"respiratory (?:depression|ceiling|risk)", re.IGNORECASE),
    ),
)


def audit_claim_text(compound: str, claim: str) -> LegacyClaimFinding:
    """Flag a legacy claim for evidence review."""

    flags = [label for label, pattern in _RULES if pattern.search(claim)]

    lowered = claim.lower()
    if compound.lower() == "ketobemidone" and "antagonist" in lowered:
        flags.append("known_high_priority_receptor_direction_check")
    if compound.lower() == "herkinorin" and (
        "no tolerance" in lowered or "depend" in lowered or "arrestin" in lowered
    ):
        flags.append("biased_agonism_safety_inference_requires_review")
    if "ibogaine" in compound.lower() and "cure" in lowered:
        flags.append("therapeutic_superlative_requires_review")

    return LegacyClaimFinding(
        compound=compound,
        claim=claim,
        flags=tuple(sorted(set(flags))),
    )


_ACTIVITY_LINE = re.compile(
    r"^\s*['\"](?P<name>.+?)['\"]\s*:\s*\[(?P<claims>.+)\],?\s*$"
)


def parse_legacy_activity_file(path: str | Path) -> list[tuple[str, str]]:
    """Parse the generated parsed_activities.py shadow corpus as text."""

    records: list[tuple[str, str]] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        match = _ACTIVITY_LINE.match(raw_line)
        if not match:
            continue

        name = match.group("name")
        payload = "[" + match.group("claims") + "]"
        try:
            claims = ast.literal_eval(payload)
        except (SyntaxError, ValueError):
            records.append((name, match.group("claims")))
            continue

        for claim in claims:
            records.append((name, str(claim)))
    return records


def audit_records(records: Iterable[tuple[str, str]]) -> list[LegacyClaimFinding]:
    return [audit_claim_text(compound, claim) for compound, claim in records]


def audit_legacy_activity_file(path: str | Path) -> list[LegacyClaimFinding]:
    return audit_records(parse_legacy_activity_file(path))


def write_json_report(findings: Iterable[LegacyClaimFinding], output: str | Path) -> None:
    Path(output).write_text(
        json.dumps([finding.to_dict() for finding in findings], indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
