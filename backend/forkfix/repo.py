"""Real GitHub repositories as tasks: issue parsing, the sandbox setup script, and its result.

SWE-bench tasks come with a prebuilt image and hidden tests. A real issue has neither, so
this module builds the environment from a public repository (clone, venv, editable install)
and makes a Task with no hidden tests: the agent writes its own reproduction test instead
(``Task.repro_first``), and verify.py checks it fails on the base commit and passes on a fix.
"""

from __future__ import annotations

import json
import re
import shlex
import urllib.error
import urllib.request
from dataclasses import dataclass

from .tasks import Task

BASE_IMAGE = "python:3.11"
VENV = "/opt/venv"
REAL_ACTIVATE = f"source {VENV}/bin/activate && cd /testbed"
SETUP_TIMEOUT = 900
MAX_ISSUE_CHARS = 8000

ISSUE_URL = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+)/issues/(\d+)/?$")
REPO_URL = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")

OK = "FORKFIX_SETUP_OK"
FAILED = "FORKFIX_SETUP_FAILED"


class RepoError(ValueError):
    pass


@dataclass(frozen=True)
class IssueRef:
    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.slug}.git"

    @property
    def api_url(self) -> str:
        return f"https://api.github.com/repos/{self.slug}/issues/{self.number}"


def parse_issue_url(url: str) -> IssueRef:
    match = ISSUE_URL.match(url.strip())
    if not match:
        raise RepoError("Expected a public issue URL like https://github.com/owner/repo/issues/123.")
    return IssueRef(match.group(1), match.group(2), int(match.group(3)))


def fetch_issue(ref: IssueRef, timeout: int = 30) -> tuple[str, str]:
    """(title, body) of a public issue. Read-only and unauthenticated; pull requests are refused."""
    request = urllib.request.Request(ref.api_url, headers={"Accept": "application/vnd.github+json",
                                                           "User-Agent": "forkfix"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:  # status only: a 403 here is usually the anonymous rate limit
        raise RepoError(f"GitHub returned HTTP {error.code} for the issue; retry later or pass --issue-file.") from None
    except OSError as error:
        raise RepoError(f"Could not reach GitHub ({type(error).__name__}); pass --issue-file.") from None
    if "pull_request" in data:
        raise RepoError("That URL is a pull request, not an issue.")
    return data.get("title") or "", (data.get("body") or "")[:MAX_ISSUE_CHARS]


def setup_script(ref: IssueRef, commit: str = "") -> str:
    """Shell script for the base image: clone, pin the commit, build a venv, install the project.

    Installs try the usual extras in turn and fall back to requirements files; whichever
    succeeds first is reported. The last lines are markers that ``parse_setup`` reads.
    """
    if commit and not COMMIT.match(commit):
        raise RepoError("The commit must be a hex sha.")
    checkout = f"git checkout -q {shlex.quote(commit)}" if commit else "true"
    installs = [
        "pip install -q -e '.[test]'", "pip install -q -e '.[tests]'", "pip install -q -e '.[dev]'",
        "pip install -q -e .",
    ]
    tried = " || ".join(f"({cmd} && echo 'installed with: {cmd}')" for cmd in installs)
    groups = "for g in tests test dev; do pip install -q --group $g 2>/dev/null || true; done"  # PEP 735
    extras = ("for f in requirements-test.txt requirements-dev.txt test-requirements.txt requirements/test.txt; "
              "do [ -f \"$f\" ] && pip install -q -r \"$f\" || true; done")
    return "\n".join([
        "set +e",
        f"fail() {{ echo '{FAILED}: '\"$1\"; exit 0; }}",
        f"python -m venv {VENV} || fail 'venv'",
        f". {VENV}/bin/activate",
        "pip install -q -U pip pytest || fail 'pip bootstrap'",
        f"git clone -q {shlex.quote(ref.clone_url)} /testbed || fail 'clone'",
        "cd /testbed",
        f"{checkout} || fail 'checkout'",
        "git config --global --add safe.directory /testbed",
        f"{tried} || fail 'install'",
        groups,
        extras,
        "pytest --collect-only -q > /tmp/forkfix_collect.log 2>&1",
        "COLLECTED=$(tail -1 /tmp/forkfix_collect.log)",
        "echo \"collect_tail: $(tail -3 /tmp/forkfix_collect.log | tr '\n' '|')\"",
        "echo \"commit: $(git rev-parse HEAD)\"",
        "echo \"collected: $COLLECTED\"",
        f"echo {OK}",
    ])


@dataclass(frozen=True)
class SetupResult:
    ok: bool
    commit: str = ""
    collected: int = 0
    message: str = ""

    def summary(self) -> str:
        if not self.ok:
            return f"Setup failed: {self.message}"
        return f"Setup ok at {self.commit[:10]}; pytest collected {self.collected} tests."


def parse_setup(output: str) -> SetupResult:
    """Read the markers a setup run prints. Anything without the OK marker is a failure."""
    failed = re.search(rf"{FAILED}: (.*)", output)
    if failed:
        return SetupResult(False, message=failed.group(1).strip())
    if OK not in output:
        return SetupResult(False, message="setup did not finish (timeout or crash)")
    commit = re.search(r"^commit: ([0-9a-f]{40})", output, flags=re.MULTILINE)
    count = re.search(r"^collected: (\d+)(?:/\d+)? tests?", output, flags=re.MULTILINE)
    collected = int(count.group(1)) if count else 0
    if not collected:
        # An installed project whose tests cannot be collected gives the verifier nothing to check.
        tail = re.search(r"^collect_tail: (.*)", output, flags=re.MULTILINE)
        detail = f" (pytest said: {tail.group(1).strip()[:300]})" if tail else ""
        return SetupResult(False, commit.group(1) if commit else "", 0, "pytest collected no tests" + detail)
    return SetupResult(True, commit.group(1) if commit else "", collected)


def real_task(ref: IssueRef, title: str, body: str, commit: str) -> Task:
    """A Task for a real issue: no hidden tests, environment from setup_script, reproduction test first."""
    return Task(
        instance_id=f"{ref.owner}__{ref.repo}-{ref.number}", repo=ref.slug, base_commit=commit,
        problem_statement=f"{title}\n\n{body}".strip(), gold_patch="", test_patch="",
        fail_to_pass=(), pass_to_pass=(), activate=REAL_ACTIVATE, repro_first=True,
    )
