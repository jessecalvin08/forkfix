"""Day-2 feasibility run: linear agent vs independent samples vs branching search on SWE-bench Lite.

Spends Token Factory and Sandbox credit only with --approve; without it, prints the
plan and exits. Evidence goes to ignored reports/day2/.

    # 1. Check the grading harness on each task (sandbox runs only, no model calls)
    .\\.venv\\Scripts\\python.exe -m forkfix.run_day2 --validate-gold --approve
    # 2. The comparison itself
    .\\.venv\\Scripts\\python.exe -m forkfix.run_day2 --modes linear,sampled,branching --parallel --approve
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .agent import TokenFactoryAgent, Trajectory
from .config import REPORTS, agent_model, judge_model, sandboxes, token_factory
from .judge import TokenFactoryJudge
from .search import Search, SearchConfig
from .verify import Verifier
from .tasks import Task, grading_script, is_resolved, load_tasks, parse_pytest_report, hidden_tests_applied
from .workspace import Meter, SandboxWorkspace, Workspace, with_retries

# Small-repo pytest tasks whose environments import quickly; override with --ids.
DEFAULT_IDS = [
    "pytest-dev__pytest-7373",
    "pytest-dev__pytest-5227",
    "pytest-dev__pytest-7432",
    "pallets__flask-4045",
    "pytest-dev__pytest-5692",
]


async def grade(task: Task, workspace: Workspace, meter: Meter) -> dict:
    """Run the hidden SWE-bench tests in a throwaway fork of the candidate's snapshot."""
    started = time.monotonic()
    _, result = await workspace.run(
        grading_script(task), files={"/tmp/forkfix_test.patch": task.test_patch.encode()}, meter=meter, timeout=900,
    )
    statuses = parse_pytest_report(result.output)
    not_passing = [(t, statuses.get(t, "absent")) for t in task.fail_to_pass + task.pass_to_pass
                   if statuses.get(t) not in ("PASSED", "XFAIL")]
    applied = hidden_tests_applied(result.output)
    return {
        "seconds": round(time.monotonic() - started, 1),
        # A hidden test patch that does not apply means the candidate cannot be graded: never resolved.
        "resolved": applied and is_resolved(task, statuses),
        "test_patch_applied": applied,
        "reported_tests": len(statuses),
        # Enough to tell a real failure from a harness or parsing problem.
        "not_passing_sample": not_passing[:15],
        "output_tail": result.output[-1500:],
        "fail_to_pass_passing": sum(statuses.get(t) in ("PASSED", "XFAIL") for t in task.fail_to_pass),
        "fail_to_pass_total": len(task.fail_to_pass),
        "pass_to_pass_passing": sum(statuses.get(t) in ("PASSED", "XFAIL") for t in task.pass_to_pass),
        "pass_to_pass_total": len(task.pass_to_pass),
    }


async def validate_gold(task: Task, base: Workspace, meter: Meter) -> dict:
    """The harness is usable for a task only if the unfixed repo fails and the reference fix passes."""
    gold, applied = await base.run(
        "cd /testbed && git apply /tmp/forkfix_gold.patch", files={"/tmp/forkfix_gold.patch": task.gold_patch.encode()},
        meter=meter, timeout=120,
    )
    unfixed, fixed = await asyncio.gather(grade(task, base, meter), grade(task, gold, meter))
    return {"gold_applied": applied.exit_code == 0, "unfixed": unfixed, "gold": fixed,
            "harness_ok": applied.exit_code == 0 and not unfixed["resolved"] and fixed["resolved"]}


def _tree(trajectories: list[Trajectory]) -> list[dict]:
    return [{
        "id": t.id, "parent": t.parent_id, "born_at_step": t.born_at_step, "steps": t.steps,
        "stop_reason": t.stop_reason or "active", "score": t.score,
        # Forks inherit their parent's history; keep only this node's own steps.
        "events": [asdict(e) for e in t.events if e.step > t.born_at_step],
    } for t in trajectories]


async def run_mode(task: Task, base: Workspace, mode: str, config: SearchConfig, budget: Meter,
                   token_budget: int | None = None) -> dict:
    meter = budget.child()
    meter.max_tokens = token_budget
    agent = TokenFactoryAgent(token_factory(), agent_model())
    # Modes with several candidates choose between them; each mode pays for its own checks.
    choosing = config.width > 1
    judge = TokenFactoryJudge(token_factory(), judge_model()) if choosing else None
    verifier = Verifier(task, base) if choosing else None
    started = time.monotonic()
    result = await Search(task, agent, judge, config, meter, verifier).run(base)
    grading = budget.child(enforce=False)
    grades = await asyncio.gather(*(grade(task, c.workspace, grading) for c in result.candidates))
    by_id = {c.id: g for c, g in zip(result.candidates, grades)}
    selected = result.selected
    infra_stops = sum(t.stop_reason.startswith("infra") for t in result.all_trajectories)
    return {
        "mode": mode,
        "token_budget": token_budget,
        "attempts": sum(t.parent_id is None for t in result.all_trajectories),
        # Any trajectory lost to an unreachable service makes this mode's result invalid.
        "infra_stops": infra_stops,
        "config": asdict(config),
        "wall_seconds": round(time.monotonic() - started, 1),
        "rounds": result.rounds,
        "selected": selected.id if selected else None,
        "selected_resolved": bool(selected and by_id[selected.id]["resolved"]),
        "any_candidate_resolved": any(g["resolved"] for g in grades),
        "candidates": [{"id": c.id, "stop_reason": c.stop_reason, "steps": c.steps, "judge_score": c.score,
                        "existing_tests": c.check.summary() if c.check else None,
                        "regressions": len(c.check.regressions) if c.check else None,
                        "broken": c.check.broken if c.check else None,
                        "patch": c.patch, **by_id[c.id]} for c in result.candidates],
        "tree": _tree(result.all_trajectories),
        "spend": meter.summary(),
        "grading_spend": grading.summary(),
    }


def summarize(record: dict) -> dict:
    """One line per task for the run summary."""
    line = {"instance_id": record["instance_id"]}
    if "validation" in record:
        v = record["validation"]
        line["harness_ok"] = v["harness_ok"]
        line["grading_seconds"] = max(v["unfixed"]["seconds"], v["gold"]["seconds"])
        return line
    for mode, r in record["modes"].items():
        if "error" in r:
            line[mode] = {"error": r["error"]}
            continue
        line[mode] = {"resolved": r["selected_resolved"], "any": r["any_candidate_resolved"],
                      "tokens": r["spend"]["prompt_tokens"] + r["spend"]["completion_tokens"],
                      "spawns": r["spend"]["sandbox_spawns"], "infra_stops": r["infra_stops"]}
    # A task counts only if no mode crashed and no trajectory was lost to an unreachable service.
    line["valid"] = all("error" not in r and not r["infra_stops"] for r in record["modes"].values())
    return line


def save(name: str, data: dict, folder: str = "day2") -> str:
    out = REPORTS / folder
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{name}.json"
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return str(path)


async def main(args: argparse.Namespace) -> None:
    catalog = {t.instance_id: t for t in load_tasks(pytest_only=False)}
    if args.ids:
        ids = args.ids.split(",")
    elif args.ids_file:
        ids = json.loads(Path(args.ids_file).read_text(encoding="utf-8"))["tasks"]
    elif args.pool == "heldout":
        # Every pytest-based task except the ones used during development.
        ids = [t.instance_id for t in load_tasks() if t.instance_id not in DEFAULT_IDS]
    else:
        ids = DEFAULT_IDS
    tasks = [catalog[i] for i in ids]
    folder = "validation" if args.validate_gold else "day2"
    modes = {
        "linear": SearchConfig.linear(args.max_steps),
        "sampled": SearchConfig.sampled(args.samples, args.max_steps),
        "matched": SearchConfig.matched(args.width, args.max_steps),
        "branching": SearchConfig(width=args.width, branch_factor=args.branch, max_steps=args.max_steps),
    }
    chosen = {m: modes[m] for m in args.modes.split(",")}
    if "matched" in chosen and "branching" not in chosen:
        raise SystemExit("matched needs branching in the same run: it spends what branching spent.")
    plan = {"tasks": ids, "validate_gold": args.validate_gold, "modes": {m: asdict(c) for m, c in chosen.items()},
            "agent_model": agent_model(), "judge_model": judge_model(), "max_tokens": args.max_tokens,
            "max_spawns": args.max_spawns, "parallel": args.parallel, "concurrency": args.concurrency}
    print(json.dumps(plan, indent=2))
    if not args.approve:
        print("Dry run: nothing was spent. Add --approve to run.")
        return

    budget = Meter(max_tokens=args.max_tokens, max_spawns=args.max_spawns)
    client = sandboxes()
    # Bounds concurrent tasks: Sandbox allows 8 concurrent image imports and 50 instances.
    slots = asyncio.Semaphore(args.concurrency)

    async def run_task(task: Task) -> dict:
        async with slots:
            return await _run_task(task)

    async def _run_task(task: Task) -> dict:
        base = SandboxWorkspace(await with_retries(lambda: client.images.oci(task.image), attempts=5, delay=10))
        record: dict = {"instance_id": task.instance_id, "image": task.image}
        if args.validate_gold:
            record["validation"] = await validate_gold(task, base, budget.child(enforce=False))
        else:
            first = {m: c for m, c in chosen.items() if m != "matched"}
            runs = await asyncio.gather(*(run_mode(task, base, m, c, budget) for m, c in first.items()),
                                        return_exceptions=True)
            # One mode's crash must not discard the other modes' paid results.
            record["modes"] = {m: (r if isinstance(r, dict) else {"mode": m, "error": type(r).__name__})
                               for m, r in zip(first, runs)}
            if "matched" in chosen:
                # Equal compute: independent attempts get exactly the tokens branching spent here.
                branching = record["modes"].get("branching", {})
                if "spend" in branching:
                    spent = branching["spend"]["prompt_tokens"] + branching["spend"]["completion_tokens"]
                    try:
                        record["modes"]["matched"] = await run_mode(task, base, "matched", chosen["matched"],
                                                                    budget, token_budget=spent)
                    except Exception as error:  # noqa: BLE001 - keep the other modes' results
                        record["modes"]["matched"] = {"mode": "matched", "error": type(error).__name__}
                else:
                    record["modes"]["matched"] = {"mode": "matched", "error": "NoBranchingRun"}
        print("saved", save(task.instance_id, record, folder), flush=True)
        return summarize(record)

    summary = []
    if args.parallel:
        # One task's crash must not discard the others' paid results.
        for task, outcome in zip(tasks, await asyncio.gather(*(run_task(t) for t in tasks), return_exceptions=True)):
            summary.append(outcome if isinstance(outcome, dict)
                           else {"instance_id": task.instance_id, "error": type(outcome).__name__})
    else:
        for task in tasks:
            summary.append(await run_task(task))
            if budget.exhausted():
                print("Spend limit reached; stopping before the next task.")
                break
    print(json.dumps({"summary": summary, "total_spend": budget.summary()}, indent=2))
    print("saved", save("summary", {"plan": plan, "summary": summary, "total_spend": budget.summary()}, folder))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", help="comma-separated SWE-bench Lite instance ids")
    parser.add_argument("--ids-file", help='JSON file with {"tasks": [instance ids]}, e.g. benchmark_tasks.json')
    parser.add_argument("--pool", choices=["heldout"], help="heldout: all pytest tasks not used in development")
    parser.add_argument("--concurrency", type=int, default=6, help="tasks in flight at once with --parallel")
    parser.add_argument("--modes", default="linear,branching,matched")
    parser.add_argument("--samples", type=int, default=4, help="independent attempts in sampled mode")
    parser.add_argument("--width", type=int, default=4)
    parser.add_argument("--branch", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--max-tokens", type=int, default=20_000_000, help="hard cap across the whole run")
    parser.add_argument("--max-spawns", type=int, default=3000)
    parser.add_argument("--validate-gold", action="store_true")
    parser.add_argument("--parallel", action="store_true", help="run all tasks at once")
    parser.add_argument("--approve", action="store_true", help="actually spend credits")
    asyncio.run(main(parser.parse_args()))
