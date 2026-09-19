from fastapi.testclient import TestClient

from app import nebius_client
from app.main import app
from app.policy_validation import VALIDATION_FIXTURES


client = TestClient(app)


def test_health_reports_local_demo_mode() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "local deterministic demo"}


def test_demo_comparison_returns_baseline_and_repair_evidence() -> None:
    response = client.get("/api/demo/comparison")
    payload = response.json()
    assert response.status_code == 200
    assert payload["baseline"]["metrics"]["policy_verdict"] == "unsafe"
    assert payload["repair"]["metrics"]["blocked_actions"] == 2
    assert payload["repair"]["metrics"]["benign_task_completed"] is True


def test_policy_compiler_explains_pending_nebius_setup(monkeypatch) -> None:
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.setattr(nebius_client, "load_local_configuration", lambda: None)
    response = client.post("/api/policies/compile", json={"policy_text": "The agent may edit source files but not read secrets."})
    assert response.status_code == 503
    assert "not configured yet" in response.json()["detail"]


def test_nvidia_model_filter_avoids_hard_coded_model_ids() -> None:
    models = ["Qwen/Qwen3-Coder", "nvidia/Nemotron-Example", "other/NVIDIA-helper"]
    assert nebius_client.nvidia_model_candidates(models) == ["nvidia/Nemotron-Example", "other/NVIDIA-helper"]


def test_policy_validation_endpoint_runs_fixed_local_checks() -> None:
    response = client.post("/api/policies/validate", json={"policy": {
        "version": "1",
        "rules": [rule.model_dump(mode="json") for rule in nebius_client.MANDATORY_GUARDRAILS],
    }})
    payload = response.json()
    assert response.status_code == 200
    assert payload["total_checks"] == len(VALIDATION_FIXTURES)
    assert payload["passed"] is False
    assert "not executed" in payload["message"]
