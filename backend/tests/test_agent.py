import asyncio

import pytest

from forkfix.agent import Action, ActionError, TokenFactoryAgent, execute
from forkfix.workspace import BudgetExceeded, Meter

from fakes import FakeWorkspace, fake_openai

SRC = "/testbed/src/calc.py"


def run(coro):
    return asyncio.run(coro)


def workspace(**kwargs):
    return FakeWorkspace({SRC: "def add(a, b):\n    return a - b\n"}, **kwargs)


def test_view_numbers_lines_and_starts_no_sandbox():
    meter = Meter()
    _, observation = run(execute(Action(tool="view", path="src/calc.py"), workspace(), meter))
    assert "     2      return a - b" in observation
    assert meter.spawns == 0


def test_edit_returns_a_new_snapshot_and_leaves_the_original_untouched():
    original = workspace()
    edited, observation = run(execute(
        Action(tool="edit", path="src/calc.py", old_str="a - b", new_str="a + b"), original, Meter()))
    assert observation.startswith("Edited")
    assert "a + b" in edited.fs[SRC] and "a - b" in original.fs[SRC]
    assert edited.snapshot_id != original.snapshot_id


@pytest.mark.parametrize("old, count", [("nope", 0), ("a", 3)])
def test_edit_must_match_exactly_once(old, count):
    ws = workspace()
    after, observation = run(execute(Action(tool="edit", path="src/calc.py", old_str=old, new_str="x"), ws, Meter()))
    assert f"matches {count} times" in observation and after is ws


@pytest.mark.parametrize("path", ["../etc/passwd", "/etc/passwd", "/testbed/../root/.ssh/id_rsa", ""])
def test_paths_outside_the_repository_are_refused(path):
    ws = workspace()
    after, observation = run(execute(Action(tool="create", path=path, content="x"), ws, Meter()))
    assert "must be inside /testbed" in observation and after is ws


def test_bash_output_is_clipped_with_both_ends_kept():
    ws = workspace(bash=lambda cmd, fs: (1, "START" + "x" * 20_000 + "END"))
    _, observation = run(execute(Action(tool="bash", command="python repro.py"), ws, Meter()))
    assert observation.startswith("[exit code 1]") and "START" in observation and observation.endswith("END")
    assert "characters omitted" in observation and len(observation) < 7000


def test_reading_a_missing_file_is_an_observation_not_a_crash():
    _, observation = run(execute(Action(tool="view", path="nope.py"), workspace(), Meter()))
    assert observation.startswith("Error: cannot read")


def test_spend_limit_blocks_new_sandbox_runs():
    meter = Meter(max_spawns=0)
    with pytest.raises(BudgetExceeded):
        run(execute(Action(tool="bash", command="ls"), workspace(), meter))


VALID = Action(tool="submit").model_dump_json()


def test_one_runaway_reply_is_retried_and_both_calls_are_metered():
    client, completions = fake_openai([("length", "{"), ("stop", VALID)])
    meter = Meter()
    action = run(TokenFactoryAgent(client, "m").act([], 0.0, meter))
    assert action.tool == "submit" and completions.calls == 2 and meter.tokens == 110
    # The first call thinks; the retry turns thinking off, since thinking is what runs away.
    assert "extra_body" not in completions.kwargs[0]
    assert completions.kwargs[1]["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_three_bad_replies_end_the_trajectory():
    client, _ = fake_openai([("stop", "not json"), ("length", ""), ("length", "")])
    with pytest.raises(ActionError):
        run(TokenFactoryAgent(client, "m").act([], 0.0, Meter()))


def test_the_last_retry_is_sampled_hotter_without_thinking():
    client, completions = fake_openai([("length", ""), ("length", ""), ("stop", VALID)])
    assert run(TokenFactoryAgent(client, "m").act([], 0.0, Meter())).tool == "submit"
    assert [k["temperature"] for k in completions.kwargs] == [0.0, 0.0, 0.7]
    assert "extra_body" in completions.kwargs[2]


def test_an_edit_that_breaks_python_syntax_is_rejected_without_a_sandbox_run():
    meter, ws = Meter(), workspace()
    bad = Action(tool="edit", path="src/calc.py", old_str="    return a - b", new_str="    total = a + b\n   return total")
    after, observation = run(execute(bad, ws, meter))
    assert after is ws and "would not parse" in observation and "IndentationError" in observation
    assert meter.spawns == 0


def test_non_python_files_are_not_syntax_checked():
    after, observation = run(execute(Action(tool="create", path="notes.txt", content="def ("), workspace(), Meter()))
    assert observation.startswith("Created")


# --- real-issue (strict) mode ---

def test_strict_mode_refuses_package_installs_but_benchmark_mode_allows_them():
    install = Action(tool="bash", command="pip install jsonpickle && python -m pip install -U x")
    allowed_ws, refused_ws = workspace(bash=lambda cmd, fs: (0, "installed")), workspace(bash=lambda cmd, fs: (0, "installed"))
    _, allowed = run(execute(install, allowed_ws, Meter()))
    assert "installed" in allowed
    meter = Meter()
    _, refused = run(execute(install, refused_ws, meter, strict=True))
    assert "installing packages is not allowed" in refused and meter.spawns == 0  # refused before any sandbox run
    # Reading or running things that merely mention pip is still fine.
    _, fine = run(execute(Action(tool="bash", command="pip list | grep click"), workspace(bash=lambda c, f: (0, "click 8")), Meter(), strict=True))
    assert "click 8" in fine


def test_repro_first_tasks_get_the_repro_prompt_and_strict_mode():
    from forkfix.agent import SYSTEM_PROMPT, Trajectory
    from fakes import make_task
    real = Trajectory.start(make_task(repro_first=True), workspace())
    plain = Trajectory.start(make_task(), workspace())
    assert real.strict and "forkfix_repro_test.py" in real.messages[0]["content"]
    assert "installing packages is refused" in real.messages[0]["content"]
    assert not plain.strict and plain.messages[0]["content"] == SYSTEM_PROMPT  # benchmark prompt unchanged
