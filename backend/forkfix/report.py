"""Aggregate a benchmark's per-task reports into the published results table.

Numbers in the README must come from here, not be typed by hand. Reads the newest report per
task (for the tasks in benchmark_tasks.json), refuses to include invalid tasks silently, and
writes a compact, git-tracked results/benchmark.json.

    .\\.venv\\Scripts\\python.exe -m forkfix.report
"""

from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path

from .benchmark import OUTPUT as BENCHMARK_FILE
from .config import REPORTS

RESULTS = Path(__file__).resolve().parents[2] / "results" / "benchmark.json"
# Token Factory list prices, USD per 1M tokens (input, output), checked 2026-09-25.
PRICES = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
    "nvidia/nemotron-3-super-120b-a12b": (0.30, 0.90),
}

def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar p-value for paired solved/unsolved outcomes."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(only_a, only_b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def estimate_usd(spend: dict) -> float | None:
    """List-price cost of one mode's model calls; None if a model has no known price.

    Reports keep input/output tokens per mode but only a total per model, so each model is
    assumed to have the mode's overall input/output split. It is an estimate, labelled as one.
    """
    total = spend["prompt_tokens"] + spend["completion_tokens"]
    if not total:
        return 0.0
    cost = 0.0
    for model, tokens in spend["tokens_by_model"].items():
        if model not in PRICES:
            return None
        price_in, price_out = PRICES[model]
        share = tokens / total
        cost += (spend["prompt_tokens"] * share * price_in + spend["completion_tokens"] * share * price_out) / 1e6
    return round(cost, 4)


def latest_reports(folder: Path, tasks: list[str], since: float) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        if path.name.endswith("-summary.json") or path.stat().st_mtime < since:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("instance_id") in tasks and "modes" in record:
            records[record["instance_id"]] = record
    return records


def valid(record: dict) -> bool:
    return all("error" not in m and not m.get("infra_stops") for m in record["modes"].values())


def build(records: dict[str, dict], tasks: list[str], modes: list[str] | None = None) -> dict:
    modes = sorted(set(modes) if modes is not None else
                   {m for t in tasks if t in records for m in records[t]["modes"]})
    rows, invalid = [], [t for t in tasks if t not in records or
                        any(m not in records[t]["modes"] for m in modes) or
                        not valid({"modes": {m: records[t]["modes"][m] for m in modes}})]
    for task in tasks:
        if task in invalid:
            continue
        row = {"task": task}
        for mode in modes:
            m = records[task]["modes"][mode]
            row[mode] = {
                "solved": m["selected_resolved"],
                "any_candidate": m["any_candidate_resolved"],
                "tokens": m["spend"]["prompt_tokens"] + m["spend"]["completion_tokens"],
                "sandbox_runs": m["spend"]["sandbox_spawns"],
                "attempts": m.get("attempts"),
                "estimated_usd": estimate_usd(m["spend"]),
            }
        rows.append(row)

    totals = {}
    for mode in modes:
        tokens_by_model: dict[str, int] = {}
        for task in tasks:
            if task in invalid:
                continue
            for model, n in records[task]["modes"][mode]["spend"]["tokens_by_model"].items():
                tokens_by_model[model] = tokens_by_model.get(model, 0) + n
        totals[mode] = {
            "solved": sum(r[mode]["solved"] for r in rows),
            "any_candidate": sum(r[mode]["any_candidate"] for r in rows),
            "tokens": sum(r[mode]["tokens"] for r in rows),
            "sandbox_runs": sum(r[mode]["sandbox_runs"] for r in rows),
            "estimated_usd": (None if any(r[mode]["estimated_usd"] is None for r in rows)
                              else round(sum(r[mode]["estimated_usd"] for r in rows), 2)),
        }

    def paired(a: str, b: str) -> dict:
        only_a = sum(r[a]["solved"] and not r[b]["solved"] for r in rows)
        only_b = sum(r[b]["solved"] and not r[a]["solved"] for r in rows)
        return {"only_" + a: only_a, "only_" + b: only_b, "mcnemar_p": round(mcnemar_exact(only_a, only_b), 3)}

    comparisons = {}
    if "branching" in modes:
        for other in modes:
            if other != "branching":
                comparisons[f"branching_vs_{other}"] = paired("branching", other)
    return {"tasks": len(rows), "invalid": invalid, "totals": totals, "comparisons": comparisons, "rows": rows}


def main(args: argparse.Namespace) -> None:
    tasks_files = [Path(p) for p in args.tasks_file] if args.tasks_file else [BENCHMARK_FILE]
    out = Path(args.out) if args.out else RESULTS
    tasks, records, sources = [], {}, []
    for tasks_file in tasks_files:
        benchmark = json.loads(tasks_file.read_text(encoding="utf-8"))
        if len(set(benchmark["tasks"])) != len(benchmark["tasks"]) or set(tasks) & set(benchmark["tasks"]):
            raise SystemExit("task lists must contain unique, non-overlapping tasks")
        since = tasks_file.stat().st_mtime if args.since_benchmark_file else 0.0
        records.update(latest_reports(REPORTS / "day2", benchmark["tasks"], since))
        tasks.extend(benchmark["tasks"])
        sources.append({"file": tasks_file.name, "seed": benchmark["seed"], "created": benchmark["created"]})
    modes = args.modes.split(",") if args.modes else None
    result = build(records, tasks, modes)
    result["benchmark"] = ({k: sources[0][k] for k in ("seed", "created")} if len(sources) == 1
                           else {"sources": sources})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("tasks", "invalid", "totals", "comparisons")}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-reports", dest="since_benchmark_file", action="store_false",
                        help="also use reports older than the tasks file")
    parser.add_argument("--tasks-file", nargs="+", help="one or more non-overlapping task lists (default: benchmark_tasks.json)")
    parser.add_argument("--modes", help="comma-separated modes required for every task, e.g. branching,matched")
    parser.add_argument("--out", help="where to write (default: results/benchmark.json)")
    main(parser.parse_args())
