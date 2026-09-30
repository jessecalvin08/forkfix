"""Offline stand-ins for Nebius Sandboxes and Token Factory. No network, no credits."""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable

from forkfix.agent import REPRO_PATH, STAGING, Action, ActionError
from forkfix.tasks import Task
from forkfix.workspace import Meter, RunResult

_ids = itertools.count()

BashHandler = Callable[[str, dict[str, str]], tuple[int, str]]


class FakeWorkspace:
    """An immutable in-memory filesystem that answers the scripts the agent generates."""

    def __init__(self, fs: dict[str, str], origin: dict[str, str] | None = None, bash: BashHandler | None = None,
                 grader: Callable[[dict[str, str]], str] | None = None, repo_tests: list[str] | None = None,
                 checker: Callable[[dict[str, str]], str] | None = None,
                 repro: Callable[[dict[str, str]], int] | None = None):
        self.fs, self.origin = dict(fs), dict(origin if origin is not None else fs)
        self.bash, self.grader = bash, grader
        self.repo_tests, self.checker, self.repro = repo_tests or [], checker, repro
        self.check_runs = 0
        self._id = f"snap-{next(_ids)}"

    @property
    def snapshot_id(self) -> str:
        return self._id

    def _derive(self, fs: dict[str, str]) -> FakeWorkspace:
        return FakeWorkspace(fs, self.origin, self.bash, self.grader, self.repo_tests, self.checker, self.repro)

    async def read(self, path: str) -> bytes:
        if path not in self.fs:
            raise FileNotFoundError(path)
        return self.fs[path].encode()

    async def run(self, script: str, *, timeout: int = 180, files: dict[str, bytes] | None = None,
                  meter: Meter) -> tuple[FakeWorkspace, RunResult]:
        meter.check_spawns()
        meter.add_spawn(0.001)
        files = files or {}
        if STAGING in files:
            target = re.search(r"cat /tmp/forkfix_upload > '(.+?)'", script).group(1)
            return self._derive({**self.fs, target: files[STAGING].decode()}), RunResult(0, "")
        if "git diff" in script:
            changed = sorted(p for p in self.fs if self.fs[p] != self.origin.get(p) and p.startswith("/testbed/src"))
            diff = "".join(f"--- a/{p[9:]}\n+++ b/{p[9:]}\n+{self.fs[p]}\n" for p in changed)
            return self._derive(self.fs), RunResult(0, diff)
        if "git ls-files" in script:
            return self._derive(self.fs), RunResult(0, "\n".join(self.repo_tests))
        if "forkfix_repro.log" in script:
            # exit code of pytest on the reproduction test, computed from the files it would see
            staged = files.get("/tmp/forkfix_repro_upload")
            seen = {**self.fs, REPRO_PATH: staged.decode()} if staged is not None else self.fs
            return self._derive(self.fs), RunResult(self.repro(seen) if self.repro else 0, "")
        if "forkfix_check.log" in script:
            self.check_runs += 1
            return self._derive(self.fs), RunResult(0, self.checker(self.fs) if self.checker else "")
        if "/tmp/forkfix_test.patch" in files:
            return self._derive(self.fs), RunResult(0, self.grader(self.fs) if self.grader else "")
        match = re.search(r"&& \((.*)\) 2>&1$", script, flags=re.DOTALL)
        if match and self.bash:
            code, out = self.bash(match.group(1), self.fs)
            return self._derive(self.fs), RunResult(code, out)
        return self._derive(self.fs), RunResult(0, "")


Policy = Callable[[list[dict], float], Action]


class FakeAgent:
    """Chooses actions with a plain function of (messages, temperature); counts tokens like the real one."""

    def __init__(self, policy: Policy, tokens_per_call: int = 100):
        self.policy, self.tokens_per_call, self.calls = policy, tokens_per_call, []

    async def act(self, messages: list[dict], temperature: float, meter: Meter) -> Action:
        meter.check_tokens()
        meter.add_llm("fake-agent", self.tokens_per_call, 0)
        self.calls.append(temperature)
        action = self.policy(messages, temperature)
        if action is None:
            raise ActionError("The model returned no complete action.")
        return action


@dataclass
class FakeJudge:
    scorer: Callable[[str], float]

    async def score(self, task: Task, trajectory, meter: Meter) -> float:
        meter.add_llm("fake-judge", 10, 0)
        return self.scorer(trajectory.patch)


def steps_taken(messages: list[dict]) -> int:
    return sum(1 for m in messages if m["role"] == "assistant")


def make_task(**overrides) -> Task:
    fields = dict(
        instance_id="demo__demo-1", repo="pytest-dev/pytest", base_commit="abc123",
        problem_statement="add() returns the wrong answer",
        gold_patch="--- a/src/calc.py\n+++ b/src/calc.py\n",
        test_patch="diff --git a/tests/test_calc.py b/tests/test_calc.py\n--- a/tests/test_calc.py\n+++ b/tests/test_calc.py\n",
        fail_to_pass=("tests/test_calc.py::test_add",), pass_to_pass=("tests/test_calc.py::test_sub",),
    )
    fields.update(overrides)
    return Task(**fields)


class FakeCompletions:
    """Replays (finish_reason, content) replies and records each request's arguments."""

    def __init__(self, replies):
        self.replies, self.calls, self.kwargs = list(replies), 0, []

    async def create(self, **kwargs):
        self.calls += 1
        self.kwargs.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        finish, content = reply
        return SimpleNamespace(
            choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=50, completion_tokens=5),
        )


def fake_openai(replies):
    completions = FakeCompletions(replies)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions
