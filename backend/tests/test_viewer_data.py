from forkfix.viewer_data import OBSERVATION_CHARS, export_mode, fork_points


def event(step, tool="bash", observation="ok"):
    return {"step": step, "tool": tool, "summary": f"{tool}: x", "observation": observation,
            "snapshot_id": "6ff7ef83-81a2-4ef4-a8b4-c6c5c73673f1"}


def mode():
    return {
        "selected_resolved": True, "any_candidate_resolved": True, "selected": "0.1", "attempts": 1,
        "token_budget": None, "wall_seconds": 12.5,
        "config": {"width": 4, "branch_factor": 3, "max_branch_points": 3, "max_steps": 30, "roots": 1},
        "spend": {"prompt_tokens": 70, "completion_tokens": 30, "sandbox_spawns": 5},
        "tree": [
            {"id": "0", "parent": None, "born_at_step": 0, "steps": 2, "stop_reason": "branched", "score": None,
             "events": [event(1, observation="x" * 1000), event(2, "view")]},
            {"id": "0.0", "parent": "0", "born_at_step": 2, "steps": 3, "stop_reason": "pruned", "score": 1.0,
             "events": [event(3, "edit")]},
            {"id": "0.1", "parent": "0", "born_at_step": 2, "steps": 4, "stop_reason": "submitted", "score": 9.0,
             "events": [event(3, "edit"), event(4, "submit")]},
        ],
        "candidates": [{"id": "0.1", "resolved": True, "judge_score": 9.0, "existing_tests": "3/3 pass",
                        "broken": False, "regressions": 0, "fail_to_pass_passing": 1, "fail_to_pass_total": 1,
                        "pass_to_pass_passing": 8, "pass_to_pass_total": 8, "patch": "diff --git a/x b/x"}],
    }


def test_export_keeps_tree_shape_and_trims_observations():
    out = export_mode(mode())
    assert [(n["id"], n["parent"], n["born"], n["end"], n["stop"]) for n in out["nodes"]] == [
        ("0", None, 0, 2, "branched"), ("0.0", "0", 2, 3, "pruned"), ("0.1", "0", 2, 4, "submitted")]
    first = out["nodes"][0]["events"][0]
    assert len(first["observation"]) == OBSERVATION_CHARS and first["snapshot"] == "6ff7ef83"
    assert out["tokens"] == 100 and out["sandbox_runs"] == 5 and "roots" not in out["config"]
    assert fork_points(out) == 1


def test_export_carries_candidate_grades():
    cand = export_mode(mode())["candidates"]["0.1"]
    assert cand["resolved"] and cand["fail_to_pass"] == [1, 1] and cand["pass_to_pass"] == [8, 8]
    assert cand["patch"].startswith("diff --git")
