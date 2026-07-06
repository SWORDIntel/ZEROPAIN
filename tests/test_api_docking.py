import importlib

from fastapi.testclient import TestClient


def test_dock_endpoint_uses_pipeline_and_persists_artifacts(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("RUN_BASE_DIR", str(tmp_path / "runs"))

    api_main = importlib.import_module("zeropain.api.main")
    api_main.RUN_BASE_DIR = tmp_path / "runs"
    api_main.app.dependency_overrides[api_main.get_current_user] = lambda: {
        "id": 1,
        "username": "tester",
        "role": "admin",
    }

    try:
        with TestClient(api_main.app) as client:
            response = client.post(
                "/api/dock",
                json={
                    "smiles": "CCO",
                    "receptor": "MOR",
                    "backend": "mocked",
                    "hardware": "CPU",
                    "poses_per_ligand": 2,
                },
            )
            job_response = client.get(f"/api/jobs/{response.json()['job_record_id']}")
    finally:
        api_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_record_id"] is not None
    assert payload["backend"] == "mocked"
    assert payload["device"] == "CPU"
    assert payload["poses"] == 2
    assert payload["provenance"]["engine"] == "zeropain.docking.pipeline"
    assert payload["provenance"]["decision_grade"] == "false"
    assert payload["provenance"]["input_hash"]
    assert payload["provenance"]["model_hash"]
    assert (tmp_path / "runs" / payload["job_id"] / "docking" / "scores.csv").exists()
    assert (tmp_path / "runs" / payload["job_id"] / "docking" / "telemetry.json").exists()
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"


def test_dock_endpoint_is_deterministic_for_reference_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("RUN_BASE_DIR", str(tmp_path / "runs"))

    api_main = importlib.import_module("zeropain.api.main")
    api_main.RUN_BASE_DIR = tmp_path / "runs"
    api_main.app.dependency_overrides[api_main.get_current_user] = lambda: {
        "id": 1,
        "username": "tester",
        "role": "admin",
    }

    try:
        with TestClient(api_main.app) as client:
            first = client.post("/api/dock", json={"smiles": "CCO", "poses_per_ligand": 3})
            second = client.post("/api/dock", json={"smiles": "CCO", "poses_per_ligand": 3})
    finally:
        api_main.app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["affinity"] == second.json()["affinity"]
    assert first.json()["ki"] == second.json()["ki"]
