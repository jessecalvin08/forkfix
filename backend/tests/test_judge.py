import asyncio

from forkfix.agent import Trajectory
from forkfix.judge import TokenFactoryJudge
from forkfix.workspace import Meter

from fakes import FakeWorkspace, fake_openai, make_task


def trajectory(patch="--- a/src/calc.py\n+++ b/src/calc.py\n"):
    t = Trajectory(id="0", workspace=FakeWorkspace({}), messages=[])
    t.patch = patch
    return t


def score(replies):
    client, completions = fake_openai(replies)
    value = asyncio.run(TokenFactoryJudge(client, "judge").score(make_task(), trajectory(), Meter()))
    return value, completions


def test_a_runaway_verdict_is_retried_without_thinking():
    value, completions = score([("length", ""), ("stop", '{"reason": "targeted", "score": 7}')])
    assert value == 7.0 and completions.calls == 2
    assert completions.kwargs[1]["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_scores_are_clamped_to_the_rubric():
    assert score([("stop", '{"reason": "x", "score": 42}')])[0] == 10.0


def test_two_failed_verdicts_score_zero_instead_of_crashing():
    assert score([("stop", "not json"), ("length", "")])[0] == 0.0


def test_the_judge_never_sees_the_hidden_tests():
    client, completions = fake_openai([("stop", '{"reason": "x", "score": 5}')])
    task = make_task(test_patch="+def test_secret_hidden(): assert add(2, 2) == 4\n")
    asyncio.run(TokenFactoryJudge(client, "judge").score(task, trajectory(), Meter()))
    sent = str(completions.kwargs[0]["messages"])
    assert "test_secret_hidden" not in sent and "tests/test_calc.py::test_add" not in sent


def test_a_fix_its_own_reproduction_test_does_not_prove_is_capped():
    from forkfix.judge import UNPROVEN_CAP, cap_by_repro
    from forkfix.verify import ReproCheck
    t = trajectory()
    assert cap_by_repro(10.0, t) == 10.0  # no reproduction test in play (benchmark tasks): untouched
    t.repro = ReproCheck(present=True, fails_on_base=False, passes_now=True)
    assert cap_by_repro(10.0, t) == UNPROVEN_CAP and cap_by_repro(2.0, t) == 2.0
    t.repro = ReproCheck(present=True, fails_on_base=True, passes_now=True)
    assert cap_by_repro(10.0, t) == 10.0  # proven
