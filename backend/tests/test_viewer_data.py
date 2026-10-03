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


# --- real-issue export ---

def issue_report(issue="https://github.com/o/r/issues/7", candidates=None, proven=False):
    return {
        "plan": {"issue": issue, "title": "Bug", "config": {"max_steps": 30}},
        "setup": {"commit": "c" * 40}, "total_spend": {"prompt_tokens": 900, "completion_tokens": 100, "sandbox_spawns": 12},
        "result": {"selected": "0.1", "proven": proven, "candidates": candidates if candidates is not None else [{
            "id": "0.1", "stop_reason": "submitted", "steps": 9, "judge_score": 10.0, "reproduction_ok": False,
            "reproduction": "The reproduction test does not fail on the unfixed repository, so it proves nothing.",
            "existing_tests": "41/41 pass.", "patch": "x" * 5000}]},
    }


def test_issue_export_pairs_the_judge_score_with_the_proof_verdict_and_trims_patches():
    import json
    from forkfix.viewer_data import PATCH_CHARS, export_issue, export_real_issues
    out = export_issue(issue_report(), "20260930T095914Z-x.json")
    assert out["issue"] == "o/r#7" and out["run"] == "20260930" and out["tokens"] == 1000
    cand = out["candidates"][0]
    assert cand["judge"] == 10.0 and cand["proven"] is False and len(cand["patch"]) == PATCH_CHARS
    assert "tree" not in out and out["note"] is None


def test_real_issue_index_keeps_the_newest_finished_run_per_issue_and_skips_failed_setups(tmp_path):
    import json
    from forkfix.viewer_data import export_real_issues
    reports, out = tmp_path / "fix", tmp_path / "out"
    reports.mkdir()
    failed = issue_report(); del failed["result"]
    (reports / "20260930T000001Z-a.json").write_text(json.dumps(failed))
    (reports / "20260930T000002Z-a.json").write_text(json.dumps(issue_report(candidates=[])))
    (reports / "20260930T000003Z-a.json").write_text(json.dumps(issue_report(proven=True)))
    (reports / "20260930T000004Z-b.json").write_text(json.dumps(issue_report("https://github.com/o/r/issues/8")))
    assert export_real_issues(reports, out) == 2
    index = json.loads((out / "index.json").read_text())
    assert index["issues"] == 2 and index["proven"] == 1 and index["patched"] == 2
    assert export_real_issues(tmp_path / "empty", tmp_path / "none") == 0


def test_a_proven_patch_that_breaks_an_existing_test_is_not_clean():
    from forkfix.viewer_data import export_issue
    report = issue_report()
    result = report["result"]
    cand = result["candidates"][0]
    cand.update(reproduction_ok=True, existing_tests="1 previously passing tests now fail, e.g. t::x")
    result.update(selected=cand["id"], proven=True)
    out = export_issue(report, "20261003T000000Z-x.json")
    assert out["proven"] is True and out["candidates"][0]["regressions"] is True and out["clean"] is False
    cand["existing_tests"] = "Existing tests t: 41/41 pass."
    assert export_issue(report, "20261003T000000Z-x.json")["clean"] is True


def test_a_hand_reviewed_patch_is_not_counted_even_when_clean():
    from forkfix.viewer_data import REVIEWED_NOT_A_FIX, export_issue
    issue = next(iter(REVIEWED_NOT_A_FIX))
    report = issue_report(issue=issue)
    cand = report["result"]["candidates"][0]
    cand.update(reproduction_ok=True, existing_tests="8/8 pass.")
    report["result"].update(proven=True)
    out = export_issue(report, "20261003T000000Z-x.json")
    assert out["proven"] is True and out["candidates"][0]["regressions"] is False
    assert out["clean"] is False and out["review"]
