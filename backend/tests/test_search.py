import asyncio

from forkfix.agent import Action
from forkfix.search import Search, SearchConfig
from forkfix.workspace import Meter

from fakes import FakeAgent, FakeJudge, FakeWorkspace, make_task, steps_taken

SRC = "/testbed/src/calc.py"
BUGGY = "def add(a, b):\n    return a - b\n"
FIXES = ["a + b", "b + a", "a * b"]


def run(coro):
    return asyncio.run(coro)


def base():
    return FakeWorkspace({SRC: BUGGY})


def solver(messages, temperature):
    """view, then edit (the fix depends on how many alternatives were sampled), then submit."""
    step = steps_taken(messages)
    if step == 0:
        return Action(tool="view", path="src/calc.py")
    if step == 1:
        solver.samples = getattr(solver, "samples", 0) + 1
        return Action(tool="edit", path="src/calc.py", old_str="a - b", new_str=FIXES[(solver.samples - 1) % 3])
    return Action(tool="submit")


def fresh_solver():
    solver.samples = 0
    return FakeAgent(solver)


def test_linear_agent_views_edits_submits_and_returns_its_patch():
    result = run(Search(make_task(), fresh_solver(), None, SearchConfig.linear(), Meter()).run(base()))
    assert [t.id for t in result.candidates] == ["0"]
    assert result.selected.stop_reason == "submitted" and "a + b" in result.selected.patch
    assert [e.tool for e in result.selected.events] == ["view", "edit", "submit"]


def test_step_limit_stops_the_agent_and_keeps_its_changes_as_an_answer():
    def looper(messages, temperature):
        if steps_taken(messages) == 0:
            return Action(tool="edit", path="src/calc.py", old_str="a - b", new_str="a + b")
        return Action(tool="bash", command="python repro.py")

    result = run(Search(make_task(), FakeAgent(looper), None, SearchConfig.linear(max_steps=4), Meter()).run(base()))
    assert result.selected.stop_reason == "step_limit" and result.selected.steps == 4
    assert "a + b" in result.selected.patch


def test_a_failed_model_call_ends_only_that_trajectory():
    result = run(Search(make_task(), FakeAgent(lambda m, t: None), None, SearchConfig.linear(), Meter()).run(base()))
    assert result.selected is None and result.all_trajectories[0].stop_reason.startswith("The model returned")


def test_branching_forks_distinct_edits_into_isolated_snapshots():
    agent = fresh_solver()
    config = SearchConfig(width=4, branch_factor=3)
    result = run(Search(make_task(), agent, FakeJudge(lambda patch: 1.0), config, Meter()).run(base()))
    patches = sorted(c.patch for c in result.candidates)
    assert len(patches) == 3 and all(fix in p for fix, p in zip(sorted(FIXES), patches))
    # Each fork holds only its own edit; the root snapshot is unchanged.
    assert {c.workspace.fs[SRC] for c in result.candidates} == {BUGGY.replace("a - b", f) for f in FIXES}
    assert result.all_trajectories[0].workspace.fs[SRC] == BUGGY
    assert {t.id for t in result.all_trajectories} == {"0", "0.0", "0.1", "0.2"}
    assert result.all_trajectories[0].stop_reason == "branched"
    # Alternatives are sampled hotter than the main action.
    assert agent.calls.count(0.8) == 2


def test_width_limit_prunes_with_the_judge_and_selection_prefers_the_best_submission():
    judge = FakeJudge(lambda patch: 9.0 if "b + a" in patch else 2.0)
    config = SearchConfig(width=2, branch_factor=3)
    result = run(Search(make_task(), fresh_solver(), judge, config, Meter()).run(base()))
    stops = {t.id: t.stop_reason for t in result.all_trajectories}
    assert sorted(stops.values()).count("pruned") == 1
    assert "b + a" in result.selected.patch and result.selected.score == 9.0


def test_hitting_the_spend_limit_still_collects_the_answers_already_paid_for():
    meter = Meter(max_tokens=200)  # 100 tokens per fake call: two steps fit, the third is refused
    result = run(Search(make_task(), fresh_solver(), None, SearchConfig.linear(), meter).run(base()))
    assert result.selected.stop_reason == "budget" and "a + b" in result.selected.patch
    assert meter.spawns >= 2  # the edit, plus the patch collected after the limit


def test_child_meters_charge_their_parent_and_share_its_limit():
    parent = Meter(max_spawns=1)
    child = parent.child()
    child.add_spawn(0.5)
    assert parent.spawns == 1 and parent.sandbox_cost == 0.5 and child.exhausted()
    assert not parent.child(enforce=False).exhausted()
