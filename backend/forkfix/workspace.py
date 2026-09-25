"""Immutable sandbox workspaces and a shared spend meter.

A workspace is a handle on one Nebius Sandbox snapshot. Reading a file uses the
image API and starts nothing; every command runs in a fresh instance of the
snapshot and returns a *new* workspace, leaving the original untouched. Forking
a branch is therefore free: two trajectories holding the same workspace can run
different commands and never see each other's changes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Protocol, TypeVar

from contree_sdk.sdk.exceptions.api import ApiTimeoutError, ContreeTransportError, TooManyRequestsError

RAW = {"stdout": bytes, "stderr": bytes}
MAX_CAPTURE_BYTES = 20_000


class BudgetExceeded(RuntimeError):
    pass


class InfraError(RuntimeError):
    """A Nebius service stayed unreachable. Not the agent's failure: the run must be redone."""


# Network blips and throttling. Retrying is safe: every run starts from an immutable snapshot.
RETRYABLE = (ContreeTransportError, ApiTimeoutError, TooManyRequestsError)
_T = TypeVar("_T")


async def with_retries(call: Callable[[], Awaitable[_T]], attempts: int = 8, delay: float = 5.0,
                       max_delay: float = 60.0) -> _T:
    """Retry network failures with backoff (about 5 minutes by default), then raise InfraError."""
    for attempt in range(attempts):
        try:
            return await call()
        except RETRYABLE as error:
            if attempt == attempts - 1:
                raise InfraError(f"Sandbox service unreachable ({type(error).__name__}).") from None
            await asyncio.sleep(min(delay * 2 ** attempt, max_delay))
    raise AssertionError("unreachable")


@dataclass
class Meter:
    """Counts spend for one scope; child meters also charge their parent."""

    max_tokens: int | None = None
    max_spawns: int | None = None
    parent: Meter | None = None
    enforce: bool = True
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0
    spawns: int = 0
    sandbox_cost: float = 0.0
    tokens_by_model: dict[str, int] = field(default_factory=dict)

    def child(self, enforce: bool = True) -> Meter:
        return Meter(parent=self, enforce=enforce)

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def _over(self, tokens: bool, spawns: bool) -> bool:
        if not self.enforce:
            return False
        return (
            (tokens and self.max_tokens is not None and self.tokens >= self.max_tokens)
            or (spawns and self.max_spawns is not None and self.spawns >= self.max_spawns)
            or (self.parent is not None and self.parent._over(tokens, spawns))
        )

    def exhausted(self) -> bool:
        return self._over(tokens=True, spawns=True)

    def check_tokens(self) -> None:
        """Before a model call. Sandbox runs check only the spawn limit, so an action
        whose tokens are already paid for still gets executed."""
        if self._over(tokens=True, spawns=False):
            raise BudgetExceeded("Token limit reached.")

    def check_spawns(self) -> None:
        if self._over(tokens=False, spawns=True):
            raise BudgetExceeded("Sandbox run limit reached.")

    def add_llm(self, model: str, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.llm_calls += 1
        self.tokens_by_model[model] = self.tokens_by_model.get(model, 0) + prompt + completion
        if self.parent:
            self.parent.add_llm(model, prompt, completion)

    def add_spawn(self, cost: float) -> None:
        self.spawns += 1
        self.sandbox_cost += cost
        if self.parent:
            self.parent.add_spawn(cost)

    def summary(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "llm_calls": self.llm_calls,
            "tokens_by_model": self.tokens_by_model,
            "sandbox_spawns": self.spawns,
            "sandbox_reported_cost": round(self.sandbox_cost, 6),
        }


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    output: str


class Workspace(Protocol):
    @property
    def snapshot_id(self) -> str: ...

    async def read(self, path: str) -> bytes: ...

    async def run(self, script: str, *, timeout: int = 180, files: dict[str, bytes] | None = None,
                  meter: Meter) -> tuple[Workspace, RunResult]: ...


def _text(output: bytes | str | None) -> str:
    if output is None:
        return ""
    return output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output


class SandboxWorkspace:
    """A Nebius Sandbox (ConTree) image snapshot."""

    def __init__(self, image):
        self._image = image

    @property
    def snapshot_id(self) -> str:
        return str(self._image.uuid)

    async def read(self, path: str) -> bytes:
        return await with_retries(lambda: self._image.read(path))

    async def run(self, script: str, *, timeout: int = 180, files: dict[str, bytes] | None = None,
                  meter: Meter) -> tuple[SandboxWorkspace, RunResult]:
        meter.check_spawns()
        # bash -c, not the SDK's shell mode: the scripts use `source`.
        result = await with_retries(lambda: self._image.run(
            command="bash", args=["-c", script], files=files or None, disposable=False,
            timeout=timeout, truncate_output_at=MAX_CAPTURE_BYTES, **RAW,
        ))
        meter.add_spawn(result.result.cost)
        output = _text(result.stdout) + _text(result.stderr)
        return SandboxWorkspace(result), RunResult(result.exit_code, output)
