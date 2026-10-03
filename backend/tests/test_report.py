from forkfix.report import build, estimate_usd, mcnemar_exact


def mode(solved, any_candidate=None, tokens=100, infra=0):
    return {"selected_resolved": solved, "any_candidate_resolved": solved if any_candidate is None else any_candidate,
            "infra_stops": infra, "attempts": 1,
            "spend": {"prompt_tokens": tokens, "completion_tokens": 0, "sandbox_spawns": 2,
                      "tokens_by_model": {"m": tokens}}}


def test_mcnemar_matches_hand_computed_values():
    assert mcnemar_exact(5, 1) == 14 / 64      # 2 * (C(6,0) + C(6,1)) / 2^6
    assert mcnemar_exact(5, 0) == 2 / 32
    assert mcnemar_exact(0, 0) == 1.0


def test_totals_and_paired_comparison():
    records = {
        "t1": {"modes": {"branching": mode(True), "matched": mode(False)}},
        "t2": {"modes": {"branching": mode(True), "matched": mode(True)}},
        "t3": {"modes": {"branching": mode(False), "matched": mode(False, any_candidate=True)}},
    }
    result = build(records, ["t1", "t2", "t3"])
    assert result["totals"]["branching"]["solved"] == 2 and result["totals"]["matched"]["any_candidate"] == 2
    assert result["comparisons"]["branching_vs_matched"] == {"only_branching": 1, "only_matched": 0, "mcnemar_p": 1.0}


def test_invalid_or_missing_tasks_are_listed_and_left_out_of_every_total():
    records = {
        "t1": {"modes": {"branching": mode(True), "matched": mode(False)}},
        "t2": {"modes": {"branching": mode(True, infra=1), "matched": mode(False)}},
    }
    result = build(records, ["t1", "t2", "t3"])
    assert result["invalid"] == ["t2", "t3"] and result["tasks"] == 1
    assert result["totals"]["branching"]["solved"] == 1


def test_cost_estimate_splits_each_model_like_the_mode_and_refuses_unknown_models():
    nano, sup = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "nvidia/nemotron-3-super-120b-a12b"
    spend = {"prompt_tokens": 3_000_000, "completion_tokens": 1_000_000,
             "tokens_by_model": {nano: 2_000_000, sup: 2_000_000}}
    # Each model: 1.5M in, 0.5M out. Nano 0.09 + 0.12, Super 0.45 + 0.45.
    assert estimate_usd(spend) == 1.11
    assert estimate_usd({**spend, "tokens_by_model": {"other/model": 4_000_000}}) is None
    result = build({"t1": {"modes": {"branching": mode(True)}}}, ["t1"])
    assert result["totals"]["branching"]["estimated_usd"] is None


def test_extension_combination_requires_the_same_modes_on_every_task():
    records = {
        "original": {"modes": {"linear": mode(False), "branching": mode(True), "matched": mode(False)}},
        "extension": {"modes": {"branching": mode(False), "matched": mode(True)}},
        "incomplete": {"modes": {"branching": mode(True)}},
    }
    result = build(records, list(records), ["branching", "matched"])
    assert result["tasks"] == 2
    assert result["invalid"] == ["incomplete"]
    assert set(result["totals"]) == {"branching", "matched"}
    assert result["comparisons"]["branching_vs_matched"] == {
        "only_branching": 1, "only_matched": 1, "mcnemar_p": 1.0,
    }
    assert build(records, list(records))["invalid"] == ["extension", "incomplete"]


def test_combined_cli_preserves_each_lists_report_cutoff(tmp_path, monkeypatch):
    import argparse
    import json
    import os
    import pytest
    import forkfix.report as report

    folder = tmp_path / "day2"
    folder.mkdir()
    first, extension = tmp_path / "first.json", tmp_path / "extension.json"
    # The extension list was created after the report for "new" was written; mtimes must not matter.
    for path, task, created in ((first, "original", "2026-09-27"), (extension, "new", "2026-09-28")):
        path.write_text(json.dumps({"tasks": [task], "seed": 0, "created": created}))
        os.utime(path, (200, 200) if task == "original" else (100, 100))
        record_path = folder / f"20260927-{task}.json"
        record_path.write_text(json.dumps({"instance_id": task, "modes": {
            "branching": mode(True), "matched": mode(False),
        }}))
    monkeypatch.setattr(report, "REPORTS", tmp_path)
    output = tmp_path / "combined.json"
    args = argparse.Namespace(tasks_file=[str(first), str(extension)], out=str(output),
                              since_benchmark_file=True, modes="branching,matched")
    report.main(args)
    result = json.loads(output.read_text())
    assert result["tasks"] == 1 and result["invalid"] == ["new"]
    assert [s["file"] for s in result["benchmark"]["sources"]] == ["first.json", "extension.json"]
    args.tasks_file = [str(first), str(first)]
    with pytest.raises(SystemExit, match="non-overlapping"):
        report.main(args)
