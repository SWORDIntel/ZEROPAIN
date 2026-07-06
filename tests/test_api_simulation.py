import importlib

from fastapi.testclient import TestClient


def test_simulate_endpoint_labels_heuristic_provenance(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("RUN_BASE_DIR", str(tmp_path / "runs"))

    api_main = importlib.import_module("zeropain.api.main")
    operations = importlib.import_module("zeropain.api.routes.operations")
    operations.RUN_BASE_DIR = tmp_path / "runs"
    api_main.app.dependency_overrides[api_main.get_current_user] = lambda: {
        "id": 1,
        "username": "tester",
        "role": "admin",
    }

    try:
        with TestClient(api_main.app) as client:
            response = client.post(
                "/api/simulate",
                json={
                    "run_id": "sim-test",
                    "patient_count": 5,
                    "duration_days": 1,
                    "backend": "local",
                    "batch_size": 20,
                },
            )
            job_response = client.get(f"/api/jobs/{response.json()['job_record_id']}")
            jobs_response = client.get("/api/jobs")
            export_response = client.get("/api/runs/sim-test/export")
    finally:
        api_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["signature_valid"] is True
    assert payload["job_record_id"] is not None
    assert payload["provenance"]["model"] == "population_simulation_v1"
    assert payload["provenance"]["decision_grade"] == "false"
    assert payload["provenance"]["input_hash"]
    assert payload["provenance"]["model_hash"]
    assert "Research simulation" in payload["provenance"]["warning"]
    assert (tmp_path / "runs" / "sim-test" / "simulation_provenance.json").exists()
    assert (tmp_path / "runs" / "sim-test" / "simulation_results.json").exists()
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"
    assert jobs_response.status_code == 200
    assert any(job["id"] == payload["job_record_id"] for job in jobs_response.json()["jobs"])
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "application/zip"
    assert export_response.content.startswith(b"PK")


def test_lead_protocol_preset_uses_sr_17018_sr_14968_and_opioid(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("RUN_BASE_DIR", str(tmp_path / "runs"))

    api_main = importlib.import_module("zeropain.api.main")
    operations = importlib.import_module("zeropain.api.routes.operations")
    operations.RUN_BASE_DIR = tmp_path / "runs"
    api_main.app.dependency_overrides[api_main.get_current_user] = lambda: {
        "id": 1,
        "username": "tester",
        "role": "admin",
    }

    try:
        with TestClient(api_main.app) as client:
            presets = client.get("/api/protocols/lead")
            response = client.post(
                "/api/simulate",
                json={
                    "run_id": "lead-sr-combo",
                    "preset": "sr_combo_oxycodone",
                    "patient_count": 3,
                    "duration_days": 1,
                },
            )
    finally:
        api_main.app.dependency_overrides.clear()

    assert presets.status_code == 200
    first = presets.json()["presets"][0]
    assert first["compounds"] == ["SR-17018", "SR-14968", "Oxycodone"]
    assert "not clinical guidance" in first["warning"]

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["compounds"] == ["SR-17018", "SR-14968", "Oxycodone"]
    assert payload["config"]["preset"] == "sr_combo_oxycodone"
    assert payload["signature_valid"] is True
