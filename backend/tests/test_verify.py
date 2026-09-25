import asyncio

from forkfix.agent import Action
from forkfix.search import Search, SearchConfig
from forkfix.verify import Verifier, related_tests
from forkfix.workspace import Meter

from fakes import FakeAgent, FakeJudge, FakeWorkspace, make_task, steps_taken

SRC = "/testbed/src/calc.py"
BUGGY = "def add(a, b):\n    return a - b\n"
REPO_TESTS = ["tests/test_calc.py", "tests/test_other.py", "docs/conf.py"]


def run(coro):
    return asyncio.run(coro)


def existing_tests(fs):
    """Existing tests: a module that raises on import stops the whole file from being collected;
    a changed rounding rule makes exactly one assertion fail."""
    source = fs.get(SRC, "")
    if "raise" in source:
        return "ERROR tests/test_calc.py - ValueError: broken\n"
    rounding = "FAILED" if "round(" in source else "PASSED"
    return ("PASSED tests/test_calc.py::test_sub\nPASSED tests/test_calc.py::test_mul\n"
            "PASSED tests/test_calc.py::test_div\n"
            f"{rounding} tests/test_calc.py::test_rounding - AssertionError\n")


def base():
    return FakeWorkspace({SRC: BUGGY}, repo_tests=REPO_TESTS, checker=existing_tests)


def test_related_tests_come_from_source_file_names_only():
    tests = ["testing/test_skipping.py", "testing/test_mark.py", "testing/logging/test_reporting.py",
             "testing/logging/test_formatter.py", "tests/test_blueprints.py"]
    assert related_tests(["src/_pytest/skipping.py"], tests) == ["testing/test_skipping.py"]
    # No test_evaluate.py exists, so fall back to the package: mark/evaluate.py -> test_mark.py.
    assert related_tests(["src/_pytest/mark/evaluate.py"], tests) == ["testing/test_mark.py"]
    # A test directory named after the module.
    assert related_tests(["src/_pytest/logging.py"], tests) == [
        "testing/logging/test_reporting.py", "testing/logging/test_formatter.py"]
    assert related_tests(["tests/test_blueprints.py", "README.rst"], tests) == []


def test_a_patch_that_stops_the_tests_from_running_is_broken():
    verifier = Verifier(make_task(), base())
    broken = FakeWorkspace({SRC: "raise ValueError\n"}, repo_tests=REPO_TESTS, checker=existing_tests)
    check = run(verifier.check("--- a/src/calc.py\n+++ b/src/calc.py\n", broken, Meter()))
    assert check.test_files == ("tests/test_calc.py",)
    assert len(check.regressions) == 4 and check.errored == 4 and check.broken
    assert "BROKEN: 4 of 4" in check.summary()


def test_one_changed_assertion_is_evidence_for_the_judge_not_a_broken_patch():
    # pytest-5227: the correct fix changes a format that an existing test still asserts.
    verifier = Verifier(make_task(), base())
    changed = FakeWorkspace({SRC: "def add(a, b):\n    return round(a + b)\n"},
                            repo_tests=REPO_TESTS, checker=existing_tests)
    check = run(verifier.check("+++ b/src/calc.py\n", changed, Meter()))
    assert check.regressions == ("tests/test_calc.py::test_rounding",) and not check.broken
    assert "expected only if the issue asks" in check.summary()


def test_the_baseline_run_is_shared_between_candidates():
    ws = base()
    verifier = Verifier(make_task(), ws)
    patch = "+++ b/src/calc.py\n"
    fixed = FakeWorkspace({SRC: "def add(a, b):\n    return a + b\n"}, repo_tests=REPO_TESTS, checker=existing_tests)

    async def both():
        return await asyncio.gather(verifier.check(patch, fixed, Meter()), verifier.check(patch, fixed, Meter()))

    first, second = run(both())
    assert not first.broken and not second.broken and first.passed == 4
    assert ws.check_runs == 1  # the unmodified repo is tested once, not once per candidate


def test_selection_never_prefers_a_broken_patch_even_with_a_perfect_judge_score():
    def two_ways(messages, temperature):
        step = steps_taken(messages)
        if step == 0:
            two_ways.n = getattr(two_ways, "n", 0) + 1
            fix = "return a + b" if two_ways.n % 2 == 0 else "raise ValueError('broken')"
            return Action(tool="edit", path="src/calc.py", old_str="return a - b", new_str=fix)
        return Action(tool="submit")

    two_ways.n = 0
    judge = FakeJudge(lambda patch: 10.0 if "raise" in patch else 6.0)  # the judge prefers the broken one
    ws = base()
    config = SearchConfig(width=4, branch_factor=2)
    result = run(Search(make_task(), FakeAgent(two_ways), judge, config, Meter(), Verifier(make_task(), ws)).run(ws))
    assert len(result.candidates) == 2
    assert "a + b" in result.selected.patch and not result.selected.check.broken


def test_sampled_mode_runs_independent_attempts_without_branching():
    agent = FakeAgent(lambda m, t: Action(tool="edit", path="src/calc.py", old_str="a - b", new_str="a + b")
                      if steps_taken(m) == 0 else Action(tool="submit"))
    ws = base()
    config = SearchConfig.sampled(3)
    result = run(Search(make_task(), agent, FakeJudge(lambda p: 5.0), config, Meter(), Verifier(make_task(), ws)).run(ws))
    assert sorted(t.id for t in result.all_trajectories) == ["0", "1", "2"]
    assert all(t.parent_id is None for t in result.all_trajectories)
    assert len(result.candidates) == 3 and set(agent.calls) == {0.7}


def test_matched_sampling_keeps_starting_attempts_until_the_token_budget_is_spent():
    agent = FakeAgent(lambda m, t: Action(tool="edit", path="src/calc.py", old_str="a - b", new_str="a + b")
                      if steps_taken(m) == 0 else Action(tool="submit"))  # 2 calls x 100 tokens per attempt
    meter = Meter(max_tokens=1000)
    ws = base()
    result = run(Search(make_task(), agent, FakeJudge(lambda p: 5.0), SearchConfig.matched(width=2), meter,
                        Verifier(make_task(), ws)).run(ws))
    attempts = [t for t in result.all_trajectories if t.parent_id is None]
    # Attempts start two at a time; the last pair begins at 800 tokens and is cut off at 1000.
    assert len(attempts) == 6
    # The agent stops at exactly the budget; only final judging (exempt, 10 fake tokens each) exceeds it.
    assert len(agent.calls) * 100 == 1000 and meter.tokens == 1000 + 6 * 10
    assert sum(t.stop_reason == "budget" for t in attempts) == 2 and len(result.candidates) == 6


def test_matched_sampling_stops_at_the_attempt_cap():
    agent = FakeAgent(lambda m, t: Action(tool="submit"))
    result = run(Search(make_task(), agent, None, SearchConfig(width=2, roots=2, refill=True, max_roots=6),
                        Meter(max_tokens=10**9)).run(base()))
    assert len(result.all_trajectories) == 6
