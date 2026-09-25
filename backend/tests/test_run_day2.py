import asyncio

from forkfix.agent import Event, Trajectory
from forkfix.run_day2 import _tree, grade, validate_gold
from forkfix.workspace import Meter

from fakes import FakeWorkspace, make_task

SRC = "/testbed/src/calc.py"


def grader(fs):
    fixed = "a + b" in fs.get(SRC, "")
    return (f"{'PASSED' if fixed else 'FAILED'} tests/test_calc.py::test_add\n"
            "PASSED tests/test_calc.py::test_sub\n")


def test_grade_runs_hidden_tests_on_the_candidate_snapshot():
    task = make_task()
    fixed = FakeWorkspace({SRC: "return a + b"}, grader=grader)
    broken = FakeWorkspace({SRC: "return a - b"}, grader=grader)
    assert asyncio.run(grade(task, fixed, Meter()))["resolved"]
    result = asyncio.run(grade(task, broken, Meter()))
    assert not result["resolved"] and result["fail_to_pass_passing"] == 0 and result["pass_to_pass_passing"] == 1


def test_gold_validation_fails_when_the_unfixed_repo_already_passes():
    task = make_task()
    always_passing = FakeWorkspace({SRC: "return a + b"}, grader=grader)
    assert not asyncio.run(validate_gold(task, always_passing, Meter()))["harness_ok"]


def test_tree_nodes_keep_only_their_own_steps():
    root = Trajectory(id="0", workspace=FakeWorkspace({}), messages=[])
    root.events = [Event(1, "view", "view: a", "", "s1")]
    root.steps = 1
    child = root.fork("0.0")
    child.events.append(Event(2, "edit", "edit: a", "", "s2"))
    child.steps = 2
    nodes = {n["id"]: n for n in _tree([root, child])}
    assert [e["step"] for e in nodes["0"]["events"]] == [1]
    assert [e["step"] for e in nodes["0.0"]["events"]] == [2] and nodes["0.0"]["parent"] == "0"


def test_a_candidate_whose_hidden_tests_cannot_be_applied_is_never_resolved():
    from forkfix.tasks import TEST_PATCH_FAILED
    task = make_task()
    ws = FakeWorkspace({SRC: "return a + b"}, grader=lambda fs: f"{TEST_PATCH_FAILED}\n" + grader(fs))
    result = asyncio.run(grade(task, ws, Meter()))
    assert not result["resolved"] and not result["test_patch_applied"]
