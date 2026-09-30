"""SWE-bench Lite tasks: loading, image names, and hidden-test grading.

Grading follows the SWE-bench harness for pytest-based repositories: reset the
test files the reference test patch touches, apply that patch, run
``pytest -rA`` on those files, and count the task resolved only if every
FAIL_TO_PASS and PASS_TO_PASS test passes. The agent never sees these tests.
"""

from __future__ import annotations

import json
import re
import shlex
import urllib.request
from dataclasses import dataclass

from .config import REPORTS

DATASET_URL = (
    "https://datasets-server.huggingface.co/rows?dataset=princeton-nlp/SWE-bench_Lite"
    "&config=default&split=test&offset={offset}&length=100"
)
CACHE = REPORTS / "swe_bench_lite.json"

# django and sympy use their own test runners; everything else runs under pytest.
PYTEST_REPOS = frozenset({
    "astropy/astropy", "matplotlib/matplotlib", "mwaskom/seaborn", "pallets/flask",
    "psf/requests", "pydata/xarray", "pylint-dev/pylint", "pytest-dev/pytest",
    "scikit-learn/scikit-learn", "sphinx-doc/sphinx",
})

ACTIVATE = "source /opt/miniconda3/bin/activate testbed && cd /testbed"
PASSING = frozenset({"PASSED", "XFAIL"})


@dataclass(frozen=True)
class Task:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    gold_patch: str
    test_patch: str
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    # Real-repository tasks (repo.py) override these; SWE-bench tasks keep the defaults.
    activate: str = ACTIVATE
    image_ref: str = ""  # a ready snapshot image name, when not derived from the instance id
    repro_first: bool = False  # the agent writes a failing reproduction test before fixing

    @classmethod
    def from_row(cls, row: dict) -> Task:
        return cls(
            instance_id=row["instance_id"],
            repo=row["repo"],
            base_commit=row["base_commit"],
            problem_statement=row["problem_statement"],
            gold_patch=row["patch"],
            test_patch=row["test_patch"],
            fail_to_pass=tuple(json.loads(row["FAIL_TO_PASS"])),
            pass_to_pass=tuple(json.loads(row["PASS_TO_PASS"])),
        )

    @property
    def image(self) -> str:
        if self.image_ref:
            return self.image_ref
        # SWE-bench's Docker Hub naming: lower-cased, "__" becomes "_1776_".
        return f"swebench/sweb.eval.x86_64.{self.instance_id.lower().replace('__', '_1776_')}:latest"

    @property
    def test_files(self) -> list[str]:
        return patched_files(self.test_patch)


def load_tasks(pytest_only: bool = True) -> list[Task]:
    """The 300 public SWE-bench Lite rows, cached in ignored reports/ after the first fetch."""
    if not CACHE.exists():
        rows = []
        for offset in range(0, 300, 100):
            with urllib.request.urlopen(DATASET_URL.format(offset=offset), timeout=60) as response:
                rows += [r["row"] for r in json.load(response)["rows"]]
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(rows), encoding="utf-8")
    tasks = [Task.from_row(row) for row in json.loads(CACHE.read_text(encoding="utf-8"))]
    return [t for t in tasks if t.repo in PYTEST_REPOS] if pytest_only else tasks


def patched_files(patch: str) -> list[str]:
    files = []
    for match in re.finditer(r"^\+\+\+ b/(\S+)", patch, flags=re.MULTILINE):
        if match.group(1) not in files:
            files.append(match.group(1))
    return files


TEST_PATCH_FAILED = "FORKFIX_TEST_PATCH_FAILED"
# SWE-bench's pytest log parser recognises exactly these line prefixes.
STATUS_WORDS = ("PASSED", "FAILED", "SKIPPED", "ERROR", "XFAIL")


def grading_script(task: Task) -> str:
    """Shell script run in a fork of the candidate's snapshot; test.patch is uploaded to /tmp.

    Mirrors the SWE-bench harness (plain ``pytest -rA <files>``) so its recorded test ids match.
    """
    files = " ".join(shlex.quote(f) for f in task.test_files)
    return " && ".join([
        ACTIVATE,
        f"git checkout {task.base_commit} -- {files} 2>/dev/null || true",
        f"(git apply /tmp/forkfix_test.patch || echo {TEST_PATCH_FAILED})",
    ]) + (
        f"; pytest -rA {files} > /tmp/forkfix_tests.log 2>&1"
        # Only status lines come back, so output truncation cannot hide a result. -a: some logs
        # contain a NUL byte, and without it grep calls the file binary and prints nothing.
        f"; grep -a -E '^({'|'.join(STATUS_WORDS)})' /tmp/forkfix_tests.log"
    )


def parse_pytest_report(output: str) -> dict[str, str]:
    """Test id -> status, parsed exactly like SWE-bench's ``parse_log_pytest``.

    SWE-bench keeps only the first whitespace-separated token after the status, so a
    parametrized id containing a space is recorded truncated in FAIL_TO_PASS/PASS_TO_PASS.
    Parsing the same way is what makes those truncated ids match.
    """
    statuses: dict[str, str] = {}
    for line in output.split("\n"):  # not splitlines(): SWE-bench splits on \n only
        if not line.startswith(STATUS_WORDS):
            continue
        if line.startswith("FAILED"):
            line = line.replace(" - ", " ")
        parts = line.split()
        if len(parts) > 1:
            statuses[parts[1]] = parts[0]
    return statuses


def hidden_tests_applied(output: str) -> bool:
    return TEST_PATCH_FAILED not in output


def is_resolved(task: Task, statuses: dict[str, str]) -> bool:
    required = task.fail_to_pass + task.pass_to_pass
    return bool(required) and all(statuses.get(test) in PASSING for test in required)
