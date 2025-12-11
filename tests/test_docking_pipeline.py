from pathlib import Path

from zeropain.docking import DockingJobSpec, run_docking_job
from zeropain.docking import hardware_routing
from zeropain.docking.memshadow_bridge import publish_docking_run


def test_docking_pipeline_mocked(tmp_path):
    spec = DockingJobSpec(
        receptor="test-receptor",
        ligands=["CCO", "CCN"],
        backend="mocked",
        hardware="CPU",
        poses_per_ligand=2,
        run_dir=tmp_path,
    )
    result = run_docking_job(spec)
    assert result.status == "success"
    assert len(result.poses) == 4
    assert Path(result.artifacts["scores_csv"]).exists()
    assert Path(result.artifacts["telemetry"]).exists()


def test_router_mapping_cpu_fallback(monkeypatch, tmp_path):
    # Force router unavailable
    monkeypatch.setattr(hardware_routing, "ROUTER_AVAILABLE", False)
    spec = DockingJobSpec(
        receptor="test-receptor",
        ligands=["CCO"],
        backend=None,
        hardware=None,
        poses_per_ligand=1,
        run_dir=tmp_path,
    )
    result = run_docking_job(spec)
    assert result.backend == "python_ref"
    assert result.telemetry["device"] in {"CPU", "AUTO"}


def test_memshadow_publish_stub(tmp_path):
    spec = DockingJobSpec(
        receptor="test-receptor",
        ligands=["CCO"],
        backend="mocked",
        hardware="CPU",
        poses_per_ligand=1,
        run_dir=tmp_path,
    )
    result = run_docking_job(spec)
    # Should not raise; publish_docking_run best-effort
    out = publish_docking_run(spec.job_id, spec.run_dir)
    assert "meta" in out and "scores" in out


def test_vector_ingest_graceful(tmp_path, monkeypatch):
    # Force vector ingestion to noop by simulating unavailable vector store
    monkeypatch.setattr("zeropain.docking.vector_ingest.VECTOR_AVAILABLE", False)
    spec = DockingJobSpec(
        receptor="test-receptor",
        ligands=["CCO"],
        backend="mocked",
        hardware="CPU",
        poses_per_ligand=1,
        run_dir=tmp_path,
    )
    result = run_docking_job(spec)
    assert result.status == "success"

