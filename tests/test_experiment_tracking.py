import json
from pathlib import Path

from utils.experiment_tracking import ExperimentTracker


def test_signature_created_and_verified(tmp_path: Path):
    tracker = ExperimentTracker(base_dir=tmp_path, run_id="test-run")
    tracker.log_metrics("stage", {"metric": 1})

    assert tracker.signature_path.exists()
    signature = json.loads(tracker.signature_path.read_text())
    assert signature["profile"] == "CNSA_2_0"
    assert signature["digest_algorithm"] == "SHA-384"
    assert signature["signature_algorithm"] == "ML-DSA-87"
    assert signature["signature_status"] == "digest_only_compatibility"
    assert signature["cnsa_2_compliant"] is False
    ok, msg = tracker.verify_signature()
    assert ok, msg
    assert "CNSA 2.0 digest envelope valid" in msg


def test_signature_detects_tamper(tmp_path: Path):
    tracker = ExperimentTracker(base_dir=tmp_path, run_id="test-run")
    tracker.log_metrics("stage", {"metric": 1})

    # Tamper with metadata
    meta_path = tracker.meta_path
    meta = json.loads(meta_path.read_text())
    meta["run_id"] = "evil"
    meta_path.write_text(json.dumps(meta))

    ok, _ = tracker.verify_signature()
    assert not ok


def test_signature_detects_artifact_tamper(tmp_path: Path):
    tracker = ExperimentTracker(base_dir=tmp_path, run_id="test-run")
    artifact = tracker.log_artifact("result.json", {"answer": 42})

    ok, msg = tracker.verify_signature()
    assert ok, msg

    payload = json.loads(artifact.read_text())
    payload["answer"] = 43
    artifact.write_text(json.dumps(payload))

    ok, _ = tracker.verify_signature()
    assert not ok


def test_signature_ignores_checkpoint_churn(tmp_path: Path):
    tracker = ExperimentTracker(base_dir=tmp_path, run_id="test-run")
    tracker.log_metrics("stage", {"metric": 1})

    checkpoint = tracker.checkpoints_dir / "batch-0.json"
    checkpoint.write_text(json.dumps({"complete": True}))

    ok, msg = tracker.verify_signature()
    assert ok, msg
