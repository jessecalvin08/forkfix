import json

from forkfix.benchmark import allocate, eligible, latest_validations, repo_of, rest, select


def validation(ok=True, seconds=10.0):
    return {"harness_ok": ok, "unfixed": {"seconds": seconds}, "gold": {"seconds": seconds}}


def test_repo_names_drop_the_issue_number():
    assert repo_of("scikit-learn__scikit-learn-13241") == "scikit-learn__scikit-learn"


def test_only_validated_tasks_that_grade_quickly_are_eligible():
    validations = {"a__a-1": validation(), "a__a-2": validation(ok=False), "a__a-3": validation(seconds=900)}
    assert eligible(validations, max_grading_seconds=300) == ["a__a-1"]


def test_allocation_is_proportional_with_at_least_one_per_repository():
    shares = allocate({"big": 60, "mid": 30, "tiny": 2}, size=20)
    assert sum(shares.values()) == 20 and shares["tiny"] >= 1 and shares["big"] > shares["mid"] > shares["tiny"]


def test_a_pool_smaller_than_the_target_is_taken_whole():
    assert allocate({"x": 3, "y": 2}, size=40) == {"x": 3, "y": 2}


def test_selection_is_reproducible_and_changes_with_the_seed():
    pool = [f"r{r}__r{r}-{i}" for r in range(3) for i in range(20)]
    assert select(pool, 12, seed=0) == select(pool, 12, seed=0)
    assert select(pool, 12, seed=0) != select(pool, 12, seed=1)
    assert len(select(pool, 12, seed=0)) == 12


def test_the_newest_validation_per_task_wins(tmp_path):
    older = {"instance_id": "a__a-1", "validation": validation(ok=False)}
    newer = {"instance_id": "a__a-1", "validation": validation(ok=True)}
    (tmp_path / "20260925T010000Z-a__a-1.json").write_text(json.dumps(older))
    (tmp_path / "20260925T020000Z-a__a-1.json").write_text(json.dumps(newer))
    (tmp_path / "20260925T020000Z-summary.json").write_text("{}")
    assert latest_validations(tmp_path)["a__a-1"]["harness_ok"] is True


def test_rest_takes_every_eligible_task_the_first_list_did_not():
    assert rest(["a-1", "b-2", "c-3", "a-4"], ["b-2"]) == ["a-1", "a-4", "c-3"]
