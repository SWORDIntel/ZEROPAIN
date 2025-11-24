import json
from pathlib import Path

from utils.experiment_tracking import ExperimentTracker


def test_signature_created_and_verified(tmp_path: Path):
    tracker = ExperimentTracker(base_dir=tmp_path, run_id="test-run")
    tracker.log_metrics("stage", {"metric": 1})

    assert tracker.signature_path.exists()
    ok, msg = tracker.verify_signature()
    assert ok, msg


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
