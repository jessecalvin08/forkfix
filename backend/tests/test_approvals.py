import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import approvals, run_sandbox
from app.approvals import ApprovalError, approve_policy, load_approval, policy_digest
from app.main import app
from app.policy_validation import VALIDATION_FIXTURES
from app.models import Decision, Policy
from app.sandbox_runner import BranchResult, RecordedAction, SandboxComparison


client = TestClient(app)
SAMPLE = Policy.model_validate_json((Path(__file__).resolve().parents[1] / "fixtures" / "sample_policy.json").read_text())
GUARDS_ONLY = {"version": "1", "rules": [{"id": "deny-net", "effect": "deny", "tool": "http_request", "path_patterns": ["**"], "reason": ""}]}


@pytest.fixture(autouse=True)
def isolated_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(approvals, "REPORTS_DIR", tmp_path)
    return tmp_path


def branch(mode):
    return BranchResult(
        mode=mode, model="nvidia/test", sandbox_image_id="img", tests_passed=True, test_exit_code=0,
        unauthorized_attempts=1, blocked_actions=1 if mode == "enforce" else 0, safety_suppressed_actions=0,
        events=[RecordedAction(step=1, tool="read_file", target=".env", policy_decision=Decision.DENY,
                               executed=mode == "observe", rule_id="deny-secret-files", result="x")],
    )


def test_digest_ignores_key_order_but_not_content() -> None:
    reordered = Policy.model_validate(json.loads(json.dumps(SAMPLE.model_dump(mode="json"), sort_keys=True)))
    assert policy_digest(reordered) == policy_digest(SAMPLE)
    changed = SAMPLE.model_copy(deep=True)
    changed.rules[0].path_patterns.append(".env")
    assert policy_digest(changed) != policy_digest(SAMPLE)


def test_approval_is_written_under_its_hash_and_reloads(isolated_reports) -> None:
    record = approve_policy(SAMPLE)
    assert record.approval_id == policy_digest(SAMPLE)
    assert (record.checks_passed, record.checks_total) == (len(VALIDATION_FIXTURES),) * 2
    assert record.approval_id in record.cli_command and "--approve" in record.cli_command
    assert (isolated_reports / "approvals" / f"{record.approval_id}.json").is_file()
    assert load_approval(record.approval_id).policy == SAMPLE


def test_failing_policy_is_not_approved_and_nothing_is_written(isolated_reports) -> None:
    response = client.post("/api/policies/approve", json={"policy": GUARDS_ONLY, "reviewed": True})
    assert response.status_code == 422
    assert response.json()["detail"]["validation"]["passed"] is False
    assert not (isolated_reports / "approvals").exists()


def test_approval_requires_explicit_review_attestation() -> None:
    policy = SAMPLE.model_dump(mode="json")
    for body in ({"policy": policy}, {"policy": policy, "reviewed": False}, {"policy": policy, "reviewed": "yes"}):
        assert client.post("/api/policies/approve", json=body).status_code == 422


def test_api_approves_and_lists_newest_first() -> None:
    first = client.post("/api/policies/approve", json={"policy": SAMPLE.model_dump(mode="json"), "reviewed": True})
    assert first.status_code == 200
    listed = client.get("/api/approvals").json()
    assert [item["approval_id"] for item in listed] == [first.json()["approval_id"]]


@pytest.mark.parametrize("bad_id", ["../../.env", "ABC", "0" * 63, "g" * 64, "0" * 64 + "/x"])
def test_approval_ids_cannot_address_other_files(bad_id) -> None:
    with pytest.raises(ApprovalError):
        load_approval(bad_id)


def test_tampered_approval_is_refused_and_hidden_from_the_list(isolated_reports) -> None:
    record = approve_policy(SAMPLE)
    path = isolated_reports / "approvals" / f"{record.approval_id}.json"
    data = json.loads(path.read_text())
    data["policy"]["rules"][0]["path_patterns"].append(".env")  # widen authority after approval
    path.write_text(json.dumps(data))
    with pytest.raises(ApprovalError, match="changed after it was approved"):
        load_approval(record.approval_id)
    assert client.get("/api/approvals").json() == []


def test_cli_refuses_tampered_approval_before_spending_anything(isolated_reports, monkeypatch) -> None:
    record = approve_policy(SAMPLE)
    path = isolated_reports / "approvals" / f"{record.approval_id}.json"
    data = json.loads(path.read_text())
    data["policy"]["rules"][0]["effect"] = "deny"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(run_sandbox, "run_sandbox_comparison", lambda policy, scenario=None: pytest.fail("Sandbox must not run"))
    with pytest.raises(SystemExit):
        run_sandbox.main(["--approval", record.approval_id, "--approve"])


def test_cli_still_requires_the_approve_flag(monkeypatch) -> None:
    record = approve_policy(SAMPLE)
    monkeypatch.setattr(run_sandbox, "run_sandbox_comparison", lambda policy, scenario=None: pytest.fail("Sandbox must not run"))
    with pytest.raises(SystemExit):
        run_sandbox.main(["--approval", record.approval_id])


def test_cli_links_evidence_to_the_approval_and_the_dashboard_reads_it(isolated_reports, monkeypatch) -> None:
    record = approve_policy(SAMPLE)
    ran = []
    monkeypatch.setattr(run_sandbox, "run_sandbox_comparison",
                        lambda policy, scenario=None: ran.append(policy) or SandboxComparison(observe=branch("observe"), enforce=branch("enforce")))
    assert run_sandbox.main(["--approval", record.approval_id, "--approve"]) == 0
    assert ran == [SAMPLE]
    files = list((isolated_reports / "evidence").glob("*.json"))
    assert len(files) == 1 and record.approval_id[:12] in files[0].name
    (isolated_reports / "evidence" / "zzz-not-evidence.json").write_text('{"hello": "world"}')
    listed = client.get("/api/evidence").json()
    assert [item["file"] for item in listed] == [files[0].name]
    assert listed[0]["evidence"]["approval_id"] == record.approval_id
    assert listed[0]["evidence"]["policy_sha256"] == record.policy_sha256


def test_evidence_is_empty_until_a_run_exists() -> None:
    assert client.get("/api/evidence").json() == []
