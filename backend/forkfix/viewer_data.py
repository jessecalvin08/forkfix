"""Export the benchmark's run trees for the static viewer in frontend/.

Uses the same report per task as forkfix.report, so the viewer and results/benchmark.json describe
the same runs. Writes frontend/public/runs/index.json (the results table plus one row per task) and
one file per task with every mode's tree, the agent's action summaries, judge scores, and each
candidate's patch and hidden-test counts. Free: reads saved reports only.

    .\\.venv\\Scripts\\python.exe -m forkfix.viewer_data
    .\\.venv\\Scripts\\python.exe -m forkfix.viewer_data --tasks-file benchmark_tasks.json benchmark_tasks_ext.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import OUTPUT as BENCHMARK_FILE
from .config import REPORTS
from .forks import summarise
from .report import build, latest_reports
from .tasks import load_tasks

OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "runs"
PROBLEM_CHARS = 1500
OBSERVATION_CHARS = 400


def export_mode(mode: dict) -> dict:
    nodes = [
        {
            "id": n["id"],
            "parent": n["parent"],
            "born": n["born_at_step"],
            "end": n["steps"],
            "stop": n["stop_reason"],
            "score": n["score"],
            "events": [
                {
                    "step": e["step"],
                    "tool": e["tool"],
                    "summary": e["summary"],
                    "observation": e["observation"][:OBSERVATION_CHARS],
                    # A short prefix is enough to show which steps share a snapshot.
                    "snapshot": (e.get("snapshot_id") or "")[:8],
                }
                for e in n["events"]
            ],
        }
        for n in mode["tree"]
    ]
    candidates = {
        c["id"]: {
            "resolved": c.get("resolved", False),
            "judge": c.get("judge_score"),
            "existing_tests": c.get("existing_tests"),
            "broken": c.get("broken", False),
            "regressions": c.get("regressions"),
            "fail_to_pass": [c.get("fail_to_pass_passing"), c.get("fail_to_pass_total")],
            "pass_to_pass": [c.get("pass_to_pass_passing"), c.get("pass_to_pass_total")],
            "patch": c.get("patch", ""),
        }
        for c in mode["candidates"]
    }
    spend = mode["spend"]
    return {
        "solved": mode["selected_resolved"],
        "any_candidate": mode["any_candidate_resolved"],
        "selected": mode["selected"],
        "attempts": mode.get("attempts"),
        "token_budget": mode.get("token_budget"),
        "tokens": spend["prompt_tokens"] + spend["completion_tokens"],
        "sandbox_runs": spend["sandbox_spawns"],
        "wall_seconds": mode.get("wall_seconds"),
        "config": {k: mode["config"][k] for k in ("width", "branch_factor", "max_branch_points", "max_steps")},
        "nodes": nodes,
        "candidates": candidates,
    }


def fork_points(mode: dict) -> int:
    return sum(n["stop"] == "branched" for n in mode["nodes"])


def main(args: argparse.Namespace) -> None:
    tasks_files = [Path(p) for p in args.tasks_file] if args.tasks_file else [BENCHMARK_FILE]
    tasks, records, sources = [], {}, []
    for tasks_file in tasks_files:
        benchmark = json.loads(tasks_file.read_text(encoding="utf-8"))
        if len(set(benchmark["tasks"])) != len(benchmark["tasks"]) or set(tasks) & set(benchmark["tasks"]):
            raise SystemExit("task lists must contain unique, non-overlapping tasks")
        records.update(latest_reports(REPORTS / "day2", benchmark["tasks"], tasks_file.stat().st_mtime))
        tasks.extend(benchmark["tasks"])
        sources.append({"file": tasks_file.name, "seed": benchmark["seed"], "created": benchmark["created"]})
    result = build(records, tasks)
    if result["invalid"]:
        raise SystemExit(f"refusing to export with invalid tasks: {result['invalid']}")
    problems = {t.instance_id: t for t in load_tasks(pytest_only=False)}

    OUTPUT.mkdir(parents=True, exist_ok=True)
    index_rows = []
    for task in tasks:
        record = records[task]
        modes = {name: export_mode(m) for name, m in record["modes"].items()}
        info = problems[task]
        statement = info.problem_statement.strip()
        payload = {
            "task": task,
            "repo": info.repo,
            "problem": statement[:PROBLEM_CHARS] + ("…" if len(statement) > PROBLEM_CHARS else ""),
            "modes": modes,
        }
        (OUTPUT / f"{task}.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        index_rows.append({
            "task": task,
            "repo": info.repo,
            "modes": {
                name: {"solved": m["solved"], "any_candidate": m["any_candidate"], "tokens": m["tokens"],
                       "forks": fork_points(m), "branches": len(m["nodes"])}
                for name, m in modes.items()
            },
        })

    index = {k: result[k] for k in ("tasks", "totals", "comparisons")}
    index["benchmark"] = sources[0] if len(sources) == 1 else {"sources": sources}
    index["forks"] = {k: v for k, v in summarise(records, tasks).items() if k != "per_task"}
    index["rows"] = index_rows
    (OUTPUT / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in OUTPUT.glob("*.json"))
    print(f"wrote {len(index_rows)} tasks + index to {OUTPUT} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-file", nargs="+",
                        help="one or more non-overlapping task lists (default: benchmark_tasks.json)")
    main(parser.parse_args())
