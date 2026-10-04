"""Checks a candidate patch against the repository's own existing tests.

This is information the agent is allowed to have: the tests already in the repo at the
base commit. Which tests to run is decided only from the *source* files the patch changed
(``foo.py`` -> ``test_foo.py``), never from the hidden SWE-bench test patch.

Two outcomes are kept apart. A candidate is *broken* when tests can no longer run (import or
collection errors) or most previously passing tests fail: the first real run had the judge
give 10/10 to such patches. A few assertions failing is different: an issue often asks for a
behaviour change that existing tests still assert (pytest-5227 changes the log format), so
those are reported to the judge as information, never as proof the patch is wrong.
"""

from __future__ import annotations

import asyncio
import hashlib
import posixpath
import shlex
from dataclasses import dataclass

from .agent import REPRO_PATH
from .tasks import ACTIVATE, PASSING, Task, parse_pytest_report, patched_files
from .workspace import Meter, Workspace

MAX_TEST_FILES = 6
WHOLE_SUITE_MAX_FILES = 12  # real-issue mode: a suite this small is run whole when no test is named after the change
CHECK_TIMEOUT = 600


BROKEN_SHARE = 0.5  # more than this share of previously passing tests failing means broken


@dataclass(frozen=True)
class Check:
    test_files: tuple[str, ...]
    regressions: tuple[str, ...]  # tests passing on the base repo that no longer pass
    passed: int
    total: int
    base_passing: int = 0
    errored: int = 0  # regressions that now error or no longer run at all

    @property
    def broken(self) -> bool:
        if not self.regressions:
            return False
        return self.errored > 0 or len(self.regressions) > BROKEN_SHARE * self.base_passing

    def summary(self) -> str:
        if not self.test_files:
            return "No existing tests were found for the changed files."
        head = f"Existing tests {', '.join(self.test_files)}: {self.passed}/{self.total} pass."
        if not self.regressions:
            return head + " None that passed before fail now."
        examples = ", ".join(self.regressions[:3])
        if self.broken:
            return head + (f" BROKEN: {len(self.regressions)} of {self.base_passing} previously passing tests "
                           f"now fail or cannot run, e.g. {examples}.")
        return head + (f" {len(self.regressions)} previously passing tests now fail, e.g. {examples}. "
                       "This is expected only if the issue asks to change the behaviour they check.")


@dataclass(frozen=True)
class ReproCheck:
    """The agent's own reproduction test: it must fail on the base repo and pass on the branch."""

    present: bool
    fails_on_base: bool = False
    passes_now: bool = False

    @property
    def ok(self) -> bool:
        return self.present and self.fails_on_base and self.passes_now

    def summary(self) -> str:
        if not self.present:
            return "No reproduction test (forkfix_repro_test.py) was written."
        if not self.fails_on_base:
            return "The reproduction test does not fail on the unfixed repository, so it proves nothing."
        if not self.passes_now:
            return "The reproduction test fails on the unfixed repository and still fails here: the bug is not fixed."
        return "The reproduction test fails on the unfixed repository and passes here: the bug is fixed."


def related_tests(changed: list[str], test_files: list[str]) -> list[str]:
    """Existing test files named after the changed source files, e.g. skipping.py -> test_skipping.py."""
    chosen: list[str] = []
    for source in changed:
        if not source.endswith(".py") or posixpath.basename(source).startswith("test_"):
            continue
        stem = posixpath.splitext(posixpath.basename(source))[0]
        parent = posixpath.basename(posixpath.dirname(source))
        if stem == "__init__":
            stem = parent
        for name in (stem, parent):
            hits = [t for t in test_files if posixpath.basename(t) == f"test_{name}.py"]
            if not hits:  # a test directory named after the module, e.g. testing/logging/
                hits = [t for t in test_files if f"/{name}/" in f"/{posixpath.dirname(t)}/"]
            if hits:
                chosen += [h for h in hits if h not in chosen]
                break
    return chosen[:MAX_TEST_FILES]


def check_script(files: list[str], activate: str = ACTIVATE) -> str:
    quoted = " ".join(shlex.quote(f) for f in files)
    return (f"{activate} && pytest -rA {quoted} > /tmp/forkfix_check.log 2>&1"
            "; grep -a -E '^(PASSED|FAILED|SKIPPED|ERROR|XFAIL)' /tmp/forkfix_check.log")


class Verifier:
    """One per task: caches the test list and the base repository's results."""

    def __init__(self, task: Task, base: Workspace):
        self.task, self.base = task, base
        self._test_files: asyncio.Task | None = None
        self._baselines: dict[tuple[str, ...], asyncio.Task] = {}
        self._repro_base: dict[str, asyncio.Task] = {}

    async def _list_tests(self, meter: Meter) -> list[str]:
        _, result = await self.base.run(
            "cd /testbed && git ls-files '*test_*.py'", meter=meter, timeout=60)
        return [line.strip() for line in result.output.splitlines() if line.strip().endswith(".py")]

    async def _statuses(self, workspace: Workspace, files: tuple[str, ...], meter: Meter) -> dict[str, str]:
        _, result = await workspace.run(check_script(list(files), self.task.activate), meter=meter, timeout=CHECK_TIMEOUT)
        return parse_pytest_report(result.output)

    async def check(self, patch: str, workspace: Workspace, meter: Meter) -> Check:
        # Cached as tasks so concurrent branches share one listing and one baseline run.
        if self._test_files is None:
            self._test_files = asyncio.ensure_future(self._list_tests(meter))
        test_files = await self._test_files
        files = tuple(related_tests(patched_files(patch), test_files))
        if not files and self.task.repro_first and 0 < len(test_files) <= WHOLE_SUITE_MAX_FILES:
            # Real issues: tests are often not named after the changed file (tabulate/__init__.py vs
            # test/test_output.py), so a small suite is run whole rather than not at all.
            files = tuple(test_files)
        if not files:
            return Check((), (), 0, 0)
        if files not in self._baselines:
            self._baselines[files] = asyncio.ensure_future(self._statuses(self.base, files, meter))
        base, now = await asyncio.gather(self._baselines[files], self._statuses(workspace, files, meter))
        regressions = tuple(t for t, s in base.items() if s in PASSING and now.get(t) not in PASSING)
        errored = sum(now.get(t) in (None, "ERROR") for t in regressions)
        return Check(files, regressions, sum(s in PASSING for s in now.values()), len(now),
                     base_passing=sum(s in PASSING for s in base.values()), errored=errored)

    async def _repro_exit(self, workspace: Workspace, source: bytes | None, meter: Meter) -> int:
        """Exit code of ``pytest`` on the reproduction test: 0 pass, 1 test failure, others are errors."""
        staged = "/tmp/forkfix_repro_upload"
        put = f"cp {staged} {shlex.quote(REPRO_PATH)} && " if source is not None else ""
        _, result = await workspace.run(
            f"{self.task.activate} && {put}pytest -q -x -p no:cacheprovider {shlex.quote(REPRO_PATH)} > /tmp/forkfix_repro.log 2>&1",
            files={staged: source} if source is not None else None, meter=meter, timeout=CHECK_TIMEOUT)
        return result.exit_code

    async def check_repro(self, workspace: Workspace, meter: Meter) -> ReproCheck:
        """Run the branch's reproduction test on the base repository and on the branch itself."""
        try:
            source = await workspace.read(REPRO_PATH)
        except Exception:  # noqa: BLE001 - a missing file is a normal outcome, not a crash
            return ReproCheck(present=False)
        digest = hashlib.sha256(source).hexdigest()
        if digest not in self._repro_base:  # identical tests from sibling branches share one base run
            self._repro_base[digest] = asyncio.ensure_future(self._repro_exit(self.base, source, meter))
        base_exit, now_exit = await asyncio.gather(self._repro_base[digest], self._repro_exit(workspace, None, meter))
        # Only a real assertion failure (exit 1) shows the bug: a crash or empty collection does not.
        return ReproCheck(present=True, fails_on_base=base_exit == 1, passes_now=now_exit == 0)
