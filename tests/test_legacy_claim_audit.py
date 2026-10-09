from pathlib import Path

from zeropain.research.legacy_claims import (
    audit_claim_text,
    audit_legacy_activity_file,
    parse_legacy_activity_file,
)


def test_absolute_claims_are_blocked_from_simulation():
    finding = audit_claim_text(
        "Example",
        "Does NOT produce addiction or dependence regardless of dose.",
    )
    assert finding.evidence_status == "legacy_unverified"
    assert finding.simulation_eligible is False
    assert "absolute_safety_or_dependence_claim" in finding.flags


def test_ketobemidone_direction_claim_is_high_priority():
    finding = audit_claim_text(
        "Ketobemidone",
        "mu opioid antagonist & NMDA antagonist.",
    )
    assert "nmda_activity" in finding.flags
    assert "known_high_priority_receptor_direction_check" in finding.flags


def test_parser_reads_generated_shadow_corpus(tmp_path: Path):
    corpus = tmp_path / "parsed_activities.py"
    corpus.write_text(
        "    'Enadoline': ['Highly selective kappa agonist. Produces dissociation...'],\n"
        "    'Naltrexone': ['Competitive antagonist at mu & kappa receptors...'],\n",
        encoding="utf-8",
    )

    records = parse_legacy_activity_file(corpus)
    assert records == [
        ("Enadoline", "Highly selective kappa agonist. Produces dissociation..."),
        ("Naltrexone", "Competitive antagonist at mu & kappa receptors..."),
    ]

    findings = audit_legacy_activity_file(corpus)
    assert len(findings) == 2
    assert "kappa_activity" in findings[0].flags
