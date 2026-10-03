from forkfix.judge import UNPROVEN_CAP
from forkfix.replay_fix import replay_issue


def report() -> dict:
    events = [
        {"tool": "bash", "summary": "bash: pip install pytest-mock", "observation": "ok"},
        {"tool": "bash", "summary": "bash: pytest forkfix_repro_test.py", "observation": "ok"},
        {"tool": "edit", "summary": "edit: a.py", "observation": "Error: old_str matches 0 times in a.py"},
    ]
    return {
        "plan": {"issue": "https://github.com/o/r/issues/1"},
        "result": {
            "tree": [{"id": "0", "stop_reason": "step_limit", "events": events},
                     {"id": "1", "stop_reason": "submitted", "events": []}],
            "candidates": [
                {"id": "1", "judge_score": 10.0, "reproduction_ok": False},
                {"id": "2", "judge_score": 3.0, "reproduction_ok": False},
                {"id": "3", "judge_score": 9.0, "reproduction_ok": True},
            ],
        },
    }


def test_replay_counts_what_the_new_rules_change():
    row = replay_issue(report())
    assert row["installs_now_refused"] == ["bash: pip install pytest-mock"]
    assert row["edit_failures_seen"] == 1
    assert row["branches_out_of_steps"] == ["0"]


def test_unproven_scores_are_capped_and_proven_ones_are_not():
    capped = {c["id"]: c["capped"] for c in replay_issue(report())["candidates"]}
    assert capped == {"1": UNPROVEN_CAP, "2": 3.0, "3": 9.0}
