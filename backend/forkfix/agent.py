"""The coding agent: one JSON action per model call, executed in a sandbox workspace.

Tools are deliberately few (bash, view, edit, create, submit). ``view`` reads
through the image API and starts no sandbox; the others each produce a new
snapshot, which is what lets the search layer fork a trajectory at any step.
"""

from __future__ import annotations

import asyncio
import json
import posixpath
import re
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

from .edits import apply_edit
from .tasks import ACTIVATE, Task
from .workspace import BudgetExceeded, InfraError, Meter, Workspace

REPO_ROOT = "/testbed"
# Nemotron thinks before acting (3-4K tokens a step was measured), and thinking counts here.
MAX_ACTION_TOKENS = 16384
THINKING_OFF = {"chat_template_kwargs": {"enable_thinking": False}}
MAX_OBSERVATION_CHARS = 6000
VIEW_LINES = 200
BASH_TIMEOUT = 180
STAGING = "/tmp/forkfix_upload"

Tool = Literal["bash", "view", "edit", "create", "submit"]

ACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "thought": {"type": "string"},
        "tool": {"type": "string", "enum": ["bash", "view", "edit", "create", "submit"]},
        "command": {"type": "string"},
        "path": {"type": "string"},
        "start_line": {"type": "integer"},
        "end_line": {"type": "integer"},
        "old_str": {"type": "string"},
        "new_str": {"type": "string"},
        "content": {"type": "string"},
    },
    "required": ["thought", "tool", "command", "path", "start_line", "end_line", "old_str", "new_str", "content"],
}

SYSTEM_PROMPT = f"""You are an autonomous software engineer fixing a GitHub issue in the repository at {REPO_ROOT}.
The project's Python environment is already active and installed. Every bash command starts in {REPO_ROOT}.

Reply with exactly one JSON action per turn. Fill only the fields your tool uses; leave the others "" or 0.
Tools:
- bash: run `command` (non-interactive, {BASH_TIMEOUT}s limit). Use it to search (grep -rn), list files, and run scripts or tests.
- view: show lines `start_line`..`end_line` of file `path` (1-based; 0 and 0 means the first {VIEW_LINES} lines).
- edit: replace `old_str` with `new_str` in file `path`. `old_str` must match exactly once, including indentation.
- create: write a new file `path` with `content`.
- submit: finish. Your repository changes are the answer.

Work like this: find the relevant code, reproduce the bug with a small script, make a minimal fix in the
library source (never edit the existing tests), re-run your script to confirm, then submit."""

REPRO_PATH = f"{REPO_ROOT}/forkfix_repro_test.py"

REPRO_SYSTEM_PROMPT = SYSTEM_PROMPT.replace(
    "Work like this: find the relevant code, reproduce the bug with a small script, make",
    "Work like this: find the relevant code, then FIRST create the file forkfix_repro_test.py: a small pytest\n"
    "test that fails on the current code because of the bug in the issue (run it with `pytest forkfix_repro_test.py`\n"
    "and confirm it fails for the right reason). The test may import only the project and packages that are already\n"
    "installed: installing packages is refused, and a test that needs one cannot be checked. Use grep -n to find code\n"
    "and view at most about 100 lines at a time: the step budget is limited. Then make",
).replace("re-run your script to confirm, then submit.",
          "re-run forkfix_repro_test.py until it passes, then submit. Keep that file in place: it is the proof of your fix.")

REPEAT_WARNING = 3  # real-issue mode: identical failing calls in a row before the agent is told to change approach
INSTALL_COMMAND = re.compile(r"\b(?:pip3?|uv\s+pip|conda|apt(?:-get)?)\s+install\b|\bpython3?\s+-m\s+pip\s+install\b")
INSTALL_REFUSED = ("Error: installing packages is not allowed. Use only the project and the packages already "
                   "installed; write the test with the standard library (for example a small custom class).")


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thought: str = ""
    tool: Tool
    command: str = ""
    path: str = ""
    start_line: int = 0
    end_line: int = 0
    old_str: str = ""
    new_str: str = ""
    content: str = ""

    def key(self) -> str:
        """Identity for de-duplicating sampled alternatives (the thought is ignored)."""
        return json.dumps(self.model_dump(exclude={"thought"}), sort_keys=True)

    def summary(self) -> str:
        if self.tool == "bash":
            return f"bash: {self.command[:120]}"
        if self.tool == "submit":
            return "submit"
        return f"{self.tool}: {self.path}"


class ActionError(RuntimeError):
    """The model could not produce a valid action."""


class AgentModel(Protocol):
    async def act(self, messages: list[dict], temperature: float, meter: Meter) -> Action: ...


def is_infra_error(error: Exception) -> bool:
    """Connection drops, timeouts, throttling and server errors: the service, not the model."""
    if isinstance(error, (APIConnectionError, APITimeoutError)):
        return True
    return isinstance(error, APIStatusError) and (error.status_code == 429 or error.status_code >= 500)


# How long to keep waiting for Token Factory to come back before giving up on a trajectory.
INFRA_PATIENCE_SECONDS = 300


class TokenFactoryAgent:
    def __init__(self, client: AsyncOpenAI, model: str, sleep=asyncio.sleep):
        self.client, self.model, self.sleep = client, model, sleep

    async def _once(self, messages: list[dict], temperature: float, meter: Meter, thinking: bool) -> Action:
        meter.check_tokens()
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=temperature, max_tokens=MAX_ACTION_TOKENS,
            response_format={"type": "json_schema",
                             "json_schema": {"name": "agent_action", "strict": True, "schema": ACTION_SCHEMA}},
            **({} if thinking else {"extra_body": THINKING_OFF}),
        )
        usage = response.usage
        meter.add_llm(self.model, getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0)
        choice = response.choices[0] if response.choices else None
        if choice is None or choice.finish_reason == "length" or not choice.message.content:
            raise ActionError("The model returned no complete action.")
        try:
            return Action.model_validate_json(choice.message.content)
        except ValidationError as error:
            raise ActionError("The model returned an invalid action.") from error

    async def act(self, messages: list[dict], temperature: float, meter: Meter) -> Action:
        # Thinking first. Thinking is what runs away, so retries skip it; the last retry is
        # also sampled hotter, because a deterministic reply that failed once may fail again.
        # A network failure is not a failed attempt: wait and retry the same attempt.
        attempts = [(True, temperature), (False, temperature), (False, max(temperature, 0.7))]
        failure: Exception | None = None
        index, waited, backoff = 0, 0.0, 5.0
        while index < len(attempts):
            thinking, temp = attempts[index]
            try:
                return await self._once(messages, temp, meter, thinking=thinking)
            except ActionError as error:
                failure, index = error, index + 1
            except (APIStatusError, APITimeoutError, APIConnectionError) as error:
                # Type names only: a provider message could carry request details.
                if not is_infra_error(error):
                    failure, index = ActionError(f"Model call failed ({type(error).__name__})."), index + 1
                    continue
                if waited >= INFRA_PATIENCE_SECONDS:
                    raise InfraError(f"Model service unreachable ({type(error).__name__}).") from None
                await self.sleep(backoff)
                waited, backoff = waited + backoff, min(backoff * 2, 60.0)
        raise failure


@dataclass
class Event:
    step: int
    tool: str
    summary: str
    observation: str
    snapshot_id: str


@dataclass
class Trajectory:
    id: str
    workspace: Workspace
    messages: list[dict]
    parent_id: str | None = None
    born_at_step: int = 0
    steps: int = 0
    branch_points: int = 0
    events: list[Event] = field(default_factory=list)
    done: bool = False
    stop_reason: str = ""
    patch: str = ""
    score: float | None = None
    check: Any = None  # a verify.Check once the patch has been run against existing tests
    repro: Any = None  # a verify.ReproCheck once the reproduction test has been run on base and on this branch
    activate: str = ACTIVATE
    strict: bool = False  # real-issue mode: no package installs, near-identical edit targets accepted

    @classmethod
    def start(cls, task: Task, workspace: Workspace, id: str = "0") -> Trajectory:
        return cls(id=id, workspace=workspace, activate=task.activate, strict=task.repro_first, messages=[
            {"role": "system", "content": REPRO_SYSTEM_PROMPT if task.repro_first else SYSTEM_PROMPT},
            {"role": "user", "content": f"<issue>\n{task.problem_statement}\n</issue>"},
        ])

    def fork(self, child_id: str) -> Trajectory:
        return replace(self, id=child_id, parent_id=self.id, born_at_step=self.steps,
                       messages=list(self.messages), events=list(self.events))

    def recent_observations(self, n: int = 2) -> str:
        return "\n---\n".join(e.observation[-1500:] for e in self.events[-n:])


def _clip(text: str, limit: int = MAX_OBSERVATION_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = limit // 3
    return f"{text[:head]}\n... [{len(text) - limit} characters omitted] ...\n{text[-(limit - head):]}"


def _abs(path: str) -> str | None:
    """Resolve a repository path; refuse anything outside /testbed."""
    if not path:
        return None
    joined = posixpath.normpath(posixpath.join(REPO_ROOT, path))
    return joined if joined == REPO_ROOT or joined.startswith(REPO_ROOT + "/") else None


async def _write(workspace: Workspace, target: str, data: bytes, meter: Meter) -> tuple[Workspace, str]:
    # Stage then `cat >` so an existing file keeps its mode; mkdir -p covers new directories.
    script = f"mkdir -p {_q(posixpath.dirname(target))} && cat {STAGING} > {_q(target)} && rm -f {STAGING}"
    new, result = await workspace.run(script, files={STAGING: data}, meter=meter, timeout=60)
    if result.exit_code != 0:
        return workspace, f"Write failed: {_clip(result.output, 500)}"
    return new, ""


def _syntax_error(path: str, source: str) -> str:
    """Reject Python that does not parse, as SWE-agent's edit guard does. Local, so no sandbox run."""
    if not path.endswith(".py"):
        return ""
    try:
        compile(source, path, "exec", dont_inherit=True)
    except SyntaxError as error:  # IndentationError included
        return f"the result would not parse ({type(error).__name__} at line {error.lineno}: {error.msg})."
    return ""


def _q(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


async def execute(action: Action, workspace: Workspace, meter: Meter,
                  activate: str = ACTIVATE, strict: bool = False) -> tuple[Workspace, str]:
    """Run one action; returns the (possibly new) workspace and the observation text."""
    if action.tool == "bash":
        if not action.command.strip():
            return workspace, "Error: empty command."
        if strict and INSTALL_COMMAND.search(action.command):
            # An install only exists in this branch's snapshot, so a test relying on it cannot be
            # re-run on the clean base repository and would prove nothing.
            return workspace, INSTALL_REFUSED
        new, result = await workspace.run(f"{activate} && ({action.command}) 2>&1", meter=meter, timeout=BASH_TIMEOUT)
        return new, _clip(f"[exit code {result.exit_code}]\n{result.output}")

    if action.tool == "submit":
        return workspace, "Submitted."

    target = _abs(action.path)
    if target is None:
        return workspace, f"Error: path must be inside {REPO_ROOT}."

    if strict and target == REPO_ROOT and action.tool in ("view", "edit"):
        # One prettytable branch sent edit on the repository root 34 times and never changed approach.
        return workspace, (f"Error: {action.path!r} is the repository root, a directory. Give the path of one "
                           f"file, for example {REPO_ROOT}/<package>/<module>.py (find it with: grep -rn 'text' .).")

    if action.tool == "create":
        if problem := _syntax_error(target, action.content):
            return workspace, f"Error: file not created; {problem}"
        new, error = await _write(workspace, target, action.content.encode(), meter)
        return new, error or f"Created {target}."

    try:
        text = (await workspace.read(target)).decode("utf-8", errors="replace")
    except InfraError:
        raise  # an unreachable service is not a missing file
    except Exception:  # noqa: BLE001 - a missing file or directory is an observation, not a crash
        return workspace, f"Error: cannot read {target} (missing, or a directory: use bash ls)."

    if action.tool == "view":
        lines = text.splitlines()
        start = max(action.start_line, 1)
        end = action.end_line if action.end_line >= start else start + VIEW_LINES - 1
        end = min(end, len(lines), start + VIEW_LINES * 2 - 1)
        body = "\n".join(f"{n:6d}  {lines[n - 1]}" for n in range(start, end + 1))
        return workspace, _clip(f"{target} ({len(lines)} lines)\n{body}")

    # edit
    outcome = apply_edit(text, action.old_str, action.new_str, parses=lambda source: not _syntax_error(target, source),
                          fuzzy=strict)
    if outcome.text is None:
        return workspace, f"Error: edit not applied; {outcome.message}"
    if problem := _syntax_error(target, outcome.text):
        return workspace, f"Error: edit not applied; {problem} Check indentation and retry."
    new, error = await _write(workspace, target, outcome.text.encode(), meter)
    return new, error or f"Edited {target}." + (f" Note: {outcome.message}" if outcome.message else "")


async def apply(trajectory: Trajectory, action: Action, meter: Meter) -> Trajectory:
    """Execute an action on a trajectory in place and record it."""
    trajectory.steps += 1
    try:
        workspace, observation = await execute(action, trajectory.workspace, meter, trajectory.activate, trajectory.strict)
    except (BudgetExceeded, InfraError):
        raise
    except Exception as error:  # noqa: BLE001 - a sandbox fault is shown to the agent, not fatal
        workspace, observation = trajectory.workspace, f"Sandbox error ({type(error).__name__}); try again or change approach."
    trajectory.workspace = workspace
    if trajectory.strict and observation.startswith("Error"):
        repeats = 1
        for event in reversed(trajectory.events):
            if event.summary != action.summary() or not event.observation.startswith("Error"):
                break
            repeats += 1
        if repeats >= REPEAT_WARNING:
            observation += f"\nNote: you have made this exact call {repeats} times and got an error each time. Change your approach."
    trajectory.messages.append({"role": "assistant", "content": action.model_dump_json()})
    trajectory.messages.append({"role": "user", "content": f"Observation:\n{observation}"})
    trajectory.events.append(Event(trajectory.steps, action.tool, action.summary(), observation[:400], workspace.snapshot_id))
    if action.tool == "submit":
        trajectory.done, trajectory.stop_reason = True, "submitted"
    return trajectory


async def collect_patch(trajectory: Trajectory, meter: Meter) -> str:
    """The trajectory's answer: tracked-file changes only, so scratch scripts are excluded."""
    _, result = await trajectory.workspace.run(f"{trajectory.activate} && git diff 2>/dev/null", meter=meter, timeout=60)
    trajectory.patch = result.output if result.exit_code == 0 else ""
    return trajectory.patch
