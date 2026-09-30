"""Scores trajectories without hidden tests, for pruning branches and picking the final answer.

The judge sees only what the agent could see: the issue, the current diff, and
the agent's latest command output. It never sees the SWE-bench tests.
"""

from __future__ import annotations

from typing import Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel, ValidationError

from .agent import MAX_ACTION_TOKENS, THINKING_OFF, Trajectory, _clip
from .tasks import Task
from .workspace import Meter

JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"reason": {"type": "string"}, "score": {"type": "integer"}},
    "required": ["reason", "score"],
}

JUDGE_PROMPT = """You review a work-in-progress fix for a GitHub issue. Rate from 0 to 10 how likely the
current changes, once finished, resolve the issue without breaking existing behaviour. Favour minimal,
targeted library changes backed by evidence that the bug is fixed; penalise edits to tests, broad
rewrites, and changes unrelated to the issue. If the existing tests are BROKEN (they no longer
run, or most now fail), score 2 or lower. If only a few existing tests now fail, decide whether
the issue asks to change the behaviour they check: if it does, that is expected, not a defect. Reply with JSON: a short reason, then the integer score."""

# Added only for tasks where the agent writes its own reproduction test, so the benchmark prompt is unchanged.
REPRO_NOTE = (" A reproduction test result is included: one that fails before the fix and passes after it is strong"
              " evidence the bug is fixed; one that still fails means it is not fixed (score 3 or lower).")


UNPROVEN_CAP = 4.0


def cap_by_repro(score: float, trajectory: Trajectory) -> float:
    """A fix whose own reproduction test does not prove it is capped: judges gave 10/10 to such patches."""
    if trajectory.repro is not None and not trajectory.repro.ok:
        return min(score, UNPROVEN_CAP)
    return score


class Verdict(BaseModel):
    reason: str
    score: int


class Judge(Protocol):
    async def score(self, task: Task, trajectory: Trajectory, meter: Meter) -> float: ...


class TokenFactoryJudge:
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client, self.model = client, model

    async def score(self, task: Task, trajectory: Trajectory, meter: Meter) -> float:
        meter.check_tokens()
        user = (
            f"<issue>\n{_clip(task.problem_statement, 6000)}\n</issue>\n"
            f"<diff>\n{_clip(trajectory.patch, 8000) or '(no changes yet)'}\n</diff>\n"
            f"<latest_output>\n{trajectory.recent_observations()}\n</latest_output>"
        )
        if trajectory.check is not None:
            user += f"\n<existing_tests>\n{trajectory.check.summary()}\n</existing_tests>"
        if trajectory.repro is not None:
            user += f"\n<reproduction_test>\n{trajectory.repro.summary()}\n</reproduction_test>"
        system = JUDGE_PROMPT + (REPRO_NOTE if trajectory.repro is not None else "")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        # Thinking first; if it runs away, one retry without it. A judge failure scores 0.
        for extra in ({}, {"extra_body": THINKING_OFF}):
            verdict = await self._ask(messages, extra, meter)
            if verdict is not None:
                return cap_by_repro(float(min(max(verdict.score, 0), 10)), trajectory)
        return 0.0

    async def _ask(self, messages: list[dict], extra: dict, meter: Meter) -> Verdict | None:
        try:
            response = await self.client.chat.completions.create(
                model=self.model, temperature=0, max_tokens=MAX_ACTION_TOKENS, messages=messages,
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "verdict", "strict": True, "schema": JUDGE_SCHEMA}},
                **extra,
            )
        except (APIStatusError, APITimeoutError, APIConnectionError):
            return None
        usage = response.usage
        meter.add_llm(self.model, getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0)
        choice = response.choices[0] if response.choices else None
        if choice is None or choice.finish_reason == "length":
            return None
        try:
            return Verdict.model_validate_json(choice.message.content or "")
        except ValidationError:
            return None
