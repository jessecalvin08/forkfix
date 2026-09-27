"""Choose the benchmark tasks from harness-validation reports, reproducibly.

Only held-out tasks are eligible (none of the five used during development), only those whose
grading harness was validated (unfixed fails, reference fix passes), and only those that grade
within a time limit. The sample is spread across repositories in proportion to their share of
the eligible pool (at least one each), with a fixed seed, so the list can be regenerated and
nobody picked tasks by hand.

    .\\.venv\\Scripts\\python.exe -m forkfix.benchmark --size 40 --seed 0
    .\\.venv\\Scripts\\python.exe -m forkfix.benchmark --rest

--rest writes benchmark_tasks_ext.json instead: every eligible task the first list did not take,
so an extension adds tasks without anyone choosing which.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .config import REPORTS

OUTPUT = Path(__file__).resolve().parents[1] / "benchmark_tasks.json"
EXTENSION = OUTPUT.with_name("benchmark_tasks_ext.json")


def repo_of(instance_id: str) -> str:
    return instance_id.rsplit("-", 1)[0]


def latest_validations(folder: Path) -> dict[str, dict]:
    """The newest validation record per task (reports are timestamped, so sorted order is time order)."""
    records: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        if path.name.endswith("-summary.json"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if "validation" in record:
            records[record["instance_id"]] = record["validation"]
    return records


def eligible(validations: dict[str, dict], max_grading_seconds: float) -> list[str]:
    return sorted(
        task for task, v in validations.items()
        if v["harness_ok"] and max(v["unfixed"]["seconds"], v["gold"]["seconds"]) <= max_grading_seconds
    )


def allocate(counts: dict[str, int], size: int) -> dict[str, int]:
    """Proportional shares with at least one per repository, largest remainders first."""
    total = sum(counts.values())
    if size >= total:
        return dict(counts)
    shares = {repo: max(1, int(size * n / total)) for repo, n in counts.items()}
    remainders = sorted(counts, key=lambda repo: (size * counts[repo] / total) % 1, reverse=True)
    i = 0
    while sum(shares.values()) < size:
        repo = remainders[i % len(remainders)]
        if shares[repo] < counts[repo]:
            shares[repo] += 1
        i += 1
    while sum(shares.values()) > size:  # the minimum of one each can overshoot
        repo = max(shares, key=lambda r: shares[r])
        shares[repo] -= 1
    return shares


def select(pool: list[str], size: int, seed: int) -> list[str]:
    by_repo: dict[str, list[str]] = defaultdict(list)
    for task in sorted(pool):
        by_repo[repo_of(task)].append(task)
    rng = random.Random(seed)
    chosen = []
    for repo, n in sorted(allocate({r: len(t) for r, t in by_repo.items()}, size).items()):
        chosen += sorted(rng.sample(by_repo[repo], n))
    return chosen


def rest(pool: list[str], taken: list[str]) -> list[str]:
    chosen = set(taken)
    return sorted(task for task in pool if task not in chosen)


def main(args: argparse.Namespace) -> None:
    validations = latest_validations(REPORTS / "validation")
    pool = eligible(validations, args.max_grading_seconds)
    if args.rest:
        tasks, output = rest(pool, json.loads(OUTPUT.read_text(encoding="utf-8"))["tasks"]), EXTENSION
        sampling = f"every eligible task not in {OUTPUT.name}"
    else:
        tasks, output = select(pool, args.size, args.seed), OUTPUT
        sampling = "proportional by repository, at least one each, fixed seed"
    output.write_text(json.dumps({
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "criteria": {
            "source": "SWE-bench Lite, pytest-based repositories, excluding the 5 development tasks",
            "harness_validated": "unfixed repository fails the hidden tests; reference fix passes them",
            "max_grading_seconds": args.max_grading_seconds,
            "sampling": sampling,
        },
        "seed": args.seed,
        "validated": len(validations),
        "eligible": len(pool),
        "tasks": tasks,
    }, indent=2) + "\n", encoding="utf-8")
    counts: dict[str, int] = defaultdict(int)
    for task in tasks:
        counts[repo_of(task)] += 1
    print(f"{len(validations)} validated, {len(pool)} eligible, {len(tasks)} chosen: {dict(counts)}")
    print(f"wrote {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-grading-seconds", type=float, default=300)
    parser.add_argument("--rest", action="store_true", help=f"write every eligible task not in {OUTPUT.name}")
    main(parser.parse_args())
