"""ECC-like shadow-verification tests."""

import json
from pathlib import Path

import pytest

from research.dissociation.verification import (
    CheckBit,
    digest,
    relation_count_not_exceed_total,
    relation_sum_close,
    verify,
)


def test_digest_is_canonical_for_mapping_order():
    a = {"b": 2, "a": [1, 3]}
    b = {"a": [1, 3], "b": 2}
    assert digest(a) == digest(b)


def test_clean_payload_has_zero_syndrome(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEROPAIN_VERIFY_LOG", str(tmp_path / "audit.jsonl"))
    payload = {
        "probability": 0.4,
        "completed": 3,
        "total": 4,
        "a": 0.25,
        "b": 0.75,
    }
    record = verify(
        payload,
        label="test.clean",
        relations=[
            relation_count_not_exceed_total("completed", "total"),
            relation_sum_close(("a", "b")),
        ],
        force=True,
    )
    assert record is not None
    assert record.syndrome == 0
    assert record.passed

    line = json.loads((tmp_path / "audit.jsonl").read_text().strip())
    assert line["label"] == "test.clean"
    assert line["syndrome"] == 0
    assert line["digest_sha256"] == digest(payload)


def test_syndrome_sets_specific_bits(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEROPAIN_VERIFY_LOG", str(tmp_path / "audit.jsonl"))
    payload = {
        "switch_probability": 1.4,
        "completed": 8,
        "total": 3,
    }
    record = verify(
        payload,
        label="test.bad",
        relations=[relation_count_not_exceed_total("completed", "total")],
        force=True,
    )
    assert record is not None
    assert record.syndrome & int(CheckBit.RANGE)
    assert record.syndrome & int(CheckBit.RELATION)
    assert not record.passed


def test_replay_mismatch_sets_replay_bit(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEROPAIN_VERIFY_LOG", str(tmp_path / "audit.jsonl"))
    payload = {"value": 1}
    record = verify(
        payload,
        label="test.replay",
        replay=lambda: {"value": 2},
        force=True,
    )
    assert record is not None
    assert record.syndrome & int(CheckBit.REPLAY)


def test_independent_checker_sets_bit(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEROPAIN_VERIFY_LOG", str(tmp_path / "audit.jsonl"))
    record = verify(
        {"value": 3},
        label="test.independent",
        independent=lambda value: (value["value"] == 4, "independent mismatch"),
        force=True,
    )
    assert record is not None
    assert record.syndrome & int(CheckBit.INDEPENDENT)


def test_strict_mode_raises_after_logging(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("ZEROPAIN_VERIFY_LOG", str(path))
    monkeypatch.setenv("ZEROPAIN_VERIFY_STRICT", "1")
    with pytest.raises(RuntimeError, match="syndrome"):
        verify(
            {"rate": 2.0},
            label="test.strict",
            force=True,
        )
    assert path.exists()


def test_disabled_returns_none(monkeypatch):
    monkeypatch.delenv("ZEROPAIN_VERIFY", raising=False)
    assert verify({"x": 1}, label="off") is None
