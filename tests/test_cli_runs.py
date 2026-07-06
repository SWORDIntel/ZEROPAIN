import zipfile

from utils.experiment_tracking import ExperimentTracker
from zeropain.cli.main import export_run, verify_run


def test_verify_and_export_run_bundle(tmp_path):
    tracker = ExperimentTracker(base_dir=tmp_path, run_id="run-a")
    tracker.record_config({"mode": "test"})
    tracker.log_artifact("artifact.json", {"value": 1})

    ok, message = verify_run(tracker.run_dir)
    assert ok, message
    assert "CNSA 2.0 digest envelope valid" in message

    bundle = export_run(tracker.run_dir)
    assert bundle.exists()
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())

    assert "run-a/metadata.json" in names
    assert "run-a/config.json" in names
    assert "run-a/artifact.json" in names
    assert "run-a/signature.sha384" in names


def test_verify_run_detects_tamper(tmp_path):
    tracker = ExperimentTracker(base_dir=tmp_path, run_id="run-a")
    artifact = tracker.log_artifact("artifact.json", {"value": 1})
    artifact.write_text('{"value": 2}')

    ok, _ = verify_run(tracker.run_dir)
    assert not ok
