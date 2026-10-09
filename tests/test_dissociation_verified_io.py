"""Verified writer and scrubber tests."""

import json

from research.dissociation.verified_io import write_json
from research.dissociation.verification_scrub import scrub


def test_verified_writer_logs_file_roundtrip(tmp_path, monkeypatch):
    result_path = tmp_path / "result.json"
    log_path = tmp_path / "verify.jsonl"
    monkeypatch.setenv("ZEROPAIN_VERIFY", "1")
    monkeypatch.setenv("ZEROPAIN_VERIFY_LOG", str(log_path))

    payload = {"switch_probability": 0.3, "nested": {"rate": 0.5}}
    write_json(result_path, payload, label="writer.test")

    assert json.loads(result_path.read_text()) == payload
    audit = json.loads(log_path.read_text().strip())
    assert audit["passed"] is True
    assert audit["metadata"]["output_path"] == str(result_path)

    result = scrub(log_path)
    assert result["passed"]
    assert result["matching"] == 1


def test_scrubber_detects_post_write_mutation(tmp_path, monkeypatch):
    result_path = tmp_path / "result.json"
    log_path = tmp_path / "verify.jsonl"
    monkeypatch.setenv("ZEROPAIN_VERIFY", "1")
    monkeypatch.setenv("ZEROPAIN_VERIFY_LOG", str(log_path))

    write_json(result_path, {"value": 1}, label="writer.tamper")
    result_path.write_text(json.dumps({"value": 2}) + "\n")

    result = scrub(log_path)
    assert not result["passed"]
    assert result["failures"][0]["status"] == "digest_mismatch"


def test_replay_only_runs_when_replay_flag_enabled(tmp_path, monkeypatch):
    result_path = tmp_path / "result.json"
    log_path = tmp_path / "verify.jsonl"
    calls = {"count": 0}

    def replay():
        calls["count"] += 1
        return {"value": 1}

    monkeypatch.setenv("ZEROPAIN_VERIFY", "1")
    monkeypatch.setenv("ZEROPAIN_VERIFY_LOG", str(log_path))
    monkeypatch.delenv("ZEROPAIN_VERIFY_REPLAY", raising=False)

    write_json(result_path, {"value": 1}, label="writer.no_replay", replay=replay)
    assert calls["count"] == 0

    monkeypatch.setenv("ZEROPAIN_VERIFY_REPLAY", "1")
    write_json(result_path, {"value": 1}, label="writer.replay", replay=replay)
    assert calls["count"] == 1
