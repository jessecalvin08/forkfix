"""Linear agent, independent samples, and branching search over sandbox snapshots, on one harness.

Linear (width 1, branch factor 1, temperature 0) is the ordinary one-attempt agent.
Sampled (``roots`` > 1, no branching) runs that many independent attempts from the start.
Matched sampling (``refill``) keeps starting fresh attempts until its token budget is spent;
given the tokens branching used on the same task, it is the equal-cost baseline that
branching has to beat to show that checkpoints, not just more attempts, are what help.
Branching runs every live trajectory one step at a time. When a trajectory is about
to change code (edit or create), it also samples alternative changes at a higher
temperature, and each distinct change continues in its own fork of the snapshot.
When more than ``width`` trajectories are alive, the best are kept. Ranking puts
candidates that do not break the repository's existing tests (verify.py) ahead of those
that do, then orders by judge score. Hidden tests are never consulted.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from .agent import Action, ActionError, AgentModel, Trajectory, apply, collect_patch
from .judge import Judge
from .tasks import Task
from .verify import Verifier
from .workspace import BudgetExceeded, InfraError, Meter, Workspace

CODE_CHANGING = frozenset({"edit", "create"})


@dataclass(frozen=True)
class SearchConfig:
    width: int = 1
    branch_factor: int = 1
    max_branch_points: int = 3
    max_steps: int = 30
    temperature: float = 0.0
    branch_temperature: float = 0.8
    roots: int = 1
    refill: bool = False  # start a new attempt whenever one ends, until the budget runs out
    max_roots: int = 16

    @classmethod
    def linear(cls, max_steps: int = 30) -> SearchConfig:
        return cls(max_steps=max_steps)

    @classmethod
    def sampled(cls, samples: int, max_steps: int = 30, temperature: float = 0.7) -> SearchConfig:
        return cls(width=samples, roots=samples, temperature=temperature, max_steps=max_steps)

    @classmethod
    def matched(cls, width: int = 4, max_steps: int = 30, temperature: float = 0.7) -> SearchConfig:
        """Independent attempts, `width` at a time, until the meter's token budget is spent."""
        return cls(width=width, roots=width, temperature=temperature, max_steps=max_steps, refill=True)


@dataclass
class SearchResult:
    selected: Trajectory | None
    candidates: list[Trajectory]
    all_trajectories: list[Trajectory]
    rounds: int


class Search:
    def __init__(self, task: Task, agent: AgentModel, judge: Judge | None, config: SearchConfig, meter: Meter,
                 verifier: Verifier | None = None):
        self.task, self.agent, self.judge, self.config, self.meter = task, agent, judge, config, meter
        self.verifier = verifier
        self._children: dict[str, int] = {}
        self.seen: list[Trajectory] = []

    def _child_id(self, parent: Trajectory) -> str:
        n = self._children.get(parent.id, 0)
        self._children[parent.id] = n + 1
        return f"{parent.id}.{n}"

    def _stop(self, trajectory: Trajectory, reason: str) -> Trajectory:
        trajectory.done, trajectory.stop_reason = True, reason
        return trajectory

    async def _alternatives(self, trajectory: Trajectory, first: Action) -> list[Action]:
        if (self.config.branch_factor <= 1 or first.tool not in CODE_CHANGING
                or trajectory.branch_points >= self.config.max_branch_points):
            return [first]
        extra = await asyncio.gather(
            *(self.agent.act(trajectory.messages, self.config.branch_temperature, self.meter)
              for _ in range(self.config.branch_factor - 1)),
            return_exceptions=True,
        )
        actions, keys = [first], {first.key()}
        for action in extra:
            if isinstance(action, Action) and action.key() not in keys:
                actions.append(action)
                keys.add(action.key())
        return actions

    async def _advance(self, trajectory: Trajectory) -> list[Trajectory]:
        """One step; returns the trajectory, or its forks when it branched."""
        if trajectory.steps >= self.config.max_steps:
            return [self._stop(trajectory, "step_limit")]
        try:
            first = await self.agent.act(trajectory.messages, self.config.temperature, self.meter)
            actions = await self._alternatives(trajectory, first)
            if len(actions) == 1:
                return [await apply(trajectory, actions[0], self.meter)]
        except ActionError as error:
            return [self._stop(trajectory, str(error))]
        except BudgetExceeded:
            return [self._stop(trajectory, "budget")]
        except InfraError as error:
            return [self._stop(trajectory, f"infra: {error}")]
        trajectory.branch_points += 1
        trajectory.stop_reason = "branched"  # an interior node of the tree from here on
        forks = [trajectory.fork(self._child_id(trajectory)) for _ in actions]
        for f in forks:
            f.stop_reason = ""
        self.seen.extend(forks)
        return list(await asyncio.gather(*(self._apply_or_stop(f, a) for f, a in zip(forks, actions))))

    async def _apply_or_stop(self, trajectory: Trajectory, action: Action) -> Trajectory:
        try:
            return await apply(trajectory, action, self.meter)
        except BudgetExceeded:
            return self._stop(trajectory, "budget")
        except InfraError as error:
            return self._stop(trajectory, f"infra: {error}")

    async def _evaluate(self, trajectories: list[Trajectory], meter: Meter) -> None:
        """Refresh each patch, check it against existing tests, then ask the judge."""
        async def one(t: Trajectory) -> None:
            await collect_patch(t, meter)
            t.check = None
            if self.verifier and t.patch.strip():
                try:
                    t.check = await self.verifier.check(t.patch, t.workspace, meter)
                except BudgetExceeded:
                    raise
                except Exception:  # noqa: BLE001 - an unverifiable candidate is ranked as unverified
                    t.check = None
            t.repro = None
            if self.verifier and self.task.repro_first:
                try:
                    t.repro = await self.verifier.check_repro(t.workspace, meter)
                except BudgetExceeded:
                    raise
                except Exception:  # noqa: BLE001 - an unrunnable reproduction test counts as no proof
                    t.repro = None
            if self.judge:
                t.score = await self.judge.score(self.task, t, meter)
        await asyncio.gather(*(one(t) for t in trajectories))

    @staticmethod
    def _rank(t: Trajectory) -> tuple:
        # A candidate that breaks the existing tests ranks below every one that does not.
        # Changed assertions are only evidence for the judge: the issue may ask for them.
        # A fix proven by its own reproduction test (fails on base, passes here) outranks an unproven one.
        return (t.check is None or not t.check.broken, bool(t.repro and t.repro.ok), t.score or 0.0)

    async def run(self, workspace: Workspace) -> SearchResult:
        roots = [Trajectory.start(self.task, workspace, id=str(i)) for i in range(self.config.roots)]
        self.seen.extend(roots)
        active, finished, rounds = list(roots), [], 0
        started = len(roots)
        try:
            while active:
                rounds += 1
                stepped = await asyncio.gather(*(self._advance(t) for t in active))
                active = []
                for group in stepped:
                    for t in group:
                        (finished if t.done else active).append(t)
                print(f"[round {rounds}] active={len(active)} finished={len(finished)} tokens={self.meter.tokens}",
                      file=sys.stderr, flush=True)
                if len(active) > self.config.width and (self.judge or self.verifier):
                    await self._evaluate(active, self.meter)
                    active.sort(key=self._rank, reverse=True)
                    for pruned in active[self.config.width:]:
                        finished.append(self._stop(pruned, "pruned"))
                    active = active[:self.config.width]
                while (self.config.refill and len(active) < self.config.width
                       and started < self.config.max_roots and not self.meter.exhausted()):
                    fresh = Trajectory.start(self.task, workspace, id=str(started))
                    started += 1
                    self.seen.append(fresh)
                    active.append(fresh)
        except BudgetExceeded:
            finished += [self._stop(t, "budget") for t in active]

        # Unfinished trajectories still count as answers if they changed code, like an autosubmit.
        # Finishing is exempt from the spend limit (still counted): otherwise hitting the
        # limit would throw away every answer the budget already paid for.
        closing = self.meter.child(enforce=False)
        answers = [t for t in finished if t.stop_reason != "pruned"]
        # Always re-read: a patch collected while scoring is stale once the trajectory moves on.
        await asyncio.gather(*(collect_patch(t, closing) for t in answers), return_exceptions=True)
        candidates = [t for t in answers if t.patch.strip()]
        selected = None
        if len(candidates) == 1 or (candidates and not (self.judge or self.verifier)):
            selected = candidates[0]
        elif candidates:
            await self._evaluate(candidates, closing)
            selected = max(candidates, key=lambda t: (self._rank(t)[0], self._rank(t)[1],
                                                       t.stop_reason == "submitted", t.score or 0.0))
        return SearchResult(selected=selected, candidates=candidates, all_trajectories=self.seen, rounds=rounds)
