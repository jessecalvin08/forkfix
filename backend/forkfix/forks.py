"""What the forks did in the benchmark's branching runs. Free: reads saved reports only.

For every fork point, each child subtree gets an outcome: "passed" (some patch in it passed
the hidden tests), "failed" (it produced graded patches, none passed) or "none" (no patch was
graded, e.g. every branch in it was pruned or stopped without changing code). A fork is
*divergent* when its children ended differently and *decisive* when at least one child passed
and at least one did not.

Child ``.0`` of a fork is the agent's own temperature-0 action; ``.1`` and ``.2`` are the
sampled alternatives. Following ``.0`` from the root gives the path the agent would have taken
without forking, so for each task branching solved we record whether that path passed too.
It is only an approximation of one attempt: model calls are not perfectly deterministic.

    .\\.venv\\Scripts\\python.exe -m forkfix.forks
    .\\.venv\\Scripts\\python.exe -m forkfix.forks --tasks-file benchmark_tasks.json benchmark_tasks_ext.json --out ..\\results\\forks_all.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import OUTPUT as BENCHMARK_FILE
from .config import REPORTS
from .report import build, latest_reports

RESULTS = Path(__file__).resolve().parents[2] / "results" / "forks.json"


def analyse(mode: dict) -> dict:
    nodes = {n["id"]: n for n in mode["tree"]}
    children: dict[str, list[str]] = {}
    for n in mode["tree"]:
        if n["parent"] is not None:
            children.setdefault(n["parent"], []).append(n["id"])
    for kids in children.values():
        kids.sort(key=lambda i: int(i.rsplit(".", 1)[1]))
    graded = {c["id"]: bool(c.get("resolved")) for c in mode["candidates"]}

    def outcome(node_id: str) -> str:
        results = {outcome(k) for k in children.get(node_id, [])}
        if node_id in graded:
            results.add("passed" if graded[node_id] else "failed")
        for best in ("passed", "failed"):
            if best in results:
                return best
        return "none"

    forks = []
    for node_id, kids in children.items():
        ends = [outcome(k) for k in kids]
        forks.append({
            "node": node_id,
            "step": nodes[node_id]["steps"],
            "children": dict(zip(kids, ends)),
            "divergent": len(set(ends)) > 1,
            "decisive": "passed" in ends and any(e != "passed" for e in ends),
            "own_action_passed": ends[0] == "passed",
        })

    greedy = next(n["id"] for n in mode["tree"] if n["parent"] is None)
    while children.get(greedy):
        greedy = children[greedy][0]
    return {"forks": forks, "own_path_leaf": greedy, "own_path_passed": graded.get(greedy, False)}


def summarise(records: dict[str, dict], tasks: list[str]) -> dict:
    per_task, all_forks = {}, []
    for task in tasks:
        modes = records[task]["modes"]
        a = analyse(modes["branching"])
        all_forks += a["forks"]
        per_task[task] = {
            "branching_solved": modes["branching"]["selected_resolved"],
            "linear_solved": modes["linear"]["selected_resolved"],
            "forks": len(a["forks"]),
            "divergent_forks": sum(f["divergent"] for f in a["forks"]),
            "decisive_forks": [f for f in a["forks"] if f["decisive"]],
            "own_path_leaf": a["own_path_leaf"],
            "own_path_passed": a["own_path_passed"],
        }
    decisive = [f for f in all_forks if f["decisive"]]
    wins = {t: r for t, r in per_task.items() if r["branching_solved"]}
    return {
        "tasks": len(tasks),
        "tasks_with_forks": sum(r["forks"] > 0 for r in per_task.values()),
        "forks": len(all_forks),
        "divergent_forks": sum(f["divergent"] for f in all_forks),
        "decisive_forks": len(decisive),
        "decisive_where_own_action_failed": sum(not f["own_action_passed"] for f in decisive),
        "branching_wins": len(wins),
        "wins_where_own_path_also_passed": sum(r["own_path_passed"] for r in wins.values()),
        "wins_needing_an_alternative": sorted(t for t, r in wins.items() if not r["own_path_passed"]),
        "per_task": per_task,
    }


def main(args: argparse.Namespace) -> None:
    tasks_files = [Path(p) for p in args.tasks_file] if args.tasks_file else [BENCHMARK_FILE]
    out = Path(args.out) if args.out else RESULTS
    tasks, records = [], {}
    for tasks_file in tasks_files:
        benchmark = json.loads(tasks_file.read_text(encoding="utf-8"))
        if len(set(benchmark["tasks"])) != len(benchmark["tasks"]) or set(tasks) & set(benchmark["tasks"]):
            raise SystemExit("task lists must contain unique, non-overlapping tasks")
        records.update(latest_reports(REPORTS / "day2", benchmark["tasks"], tasks_file.stat().st_mtime))
        tasks.extend(benchmark["tasks"])
    invalid = build(records, tasks)["invalid"]
    if invalid:
        raise SystemExit(f"refusing to analyse with invalid tasks: {invalid}")
    result = summarise(records, tasks)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_task"}, indent=2))
    for task, r in result["per_task"].items():
        if r["branching_solved"]:
            print(f"{task}: forks {r['forks']}, decisive {len(r['decisive_forks'])}, "
                  f"own path {r['own_path_leaf']} passed={r['own_path_passed']}, one attempt solved={r['linear_solved']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-file", nargs="+", help="one or more non-overlapping task lists (default: benchmark_tasks.json)")
    parser.add_argument("--out", help="where to write (default: results/forks.json)")
    main(parser.parse_args())
