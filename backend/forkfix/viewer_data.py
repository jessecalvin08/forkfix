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
FIX_OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "fix"
PATCH_CHARS = 3000
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


# Hand-written findings from checks that are not in the saved reports. Shown with their date on the page.
ANNOTATIONS = {
    "https://github.com/pallets/itsdangerous/issues/389": (
        "Checked on 2026-09-30 (sandbox only, no model calls) and again by the 2026-10-03 live run. Forwarding "
        "serializer_kwargs to loads makes the repository's own test_serializer_kwargs fail: it passes skipkeys, "
        "which json.dumps accepts and json.loads does not. serializer_kwargs is probably meant for dumps only, "
        "so this issue is likely intended behaviour, not a bug. The 2026-10-03 patch passes the agent's own test "
        "because that test checks only that the keyword arguments reach loads."
    ),
    "https://github.com/mahmoud/boltons/issues/301": (
        "Reviewed by hand on 2026-10-04 (no model calls; python -m feasibility.boltons_body_probe). The patch copies "
        "the function body by parsing source lines. It works for the issue's example, but a multi-line signature "
        "puts the signature lines in the body, and a function containing a nested def or class raises "
        "IndentationError, which the patch does not catch. It also deletes two unrelated TODO comments."
    ),
}

# Patches that passed the proof check and the existing tests but failed a manual review, so they do not count as fixes.
REVIEWED_NOT_A_FIX = {
    "https://github.com/mahmoud/boltons/issues/301": "Fails on multi-line signatures and nested functions.",
}

REGRESSION_MARK = "previously passing tests now fail"


def breaks_existing_tests(candidate: dict) -> bool:
    return REGRESSION_MARK in (candidate.get("existing_tests") or "")


def export_issue(report: dict, name: str) -> dict:
    """One real-issue run (forkfix.fix) for the viewer: candidates with their proof-check verdicts, no trees."""
    plan, spend = report["plan"], report["total_spend"]
    result = report.get("result") or {}
    candidates = [{
        "id": c["id"], "stop": c["stop_reason"], "steps": c["steps"], "judge": c["judge_score"],
        "proven": c["reproduction_ok"], "reproduction": c["reproduction"], "existing_tests": c["existing_tests"],
        "patch": (c["patch"] or "")[:PATCH_CHARS], "regressions": breaks_existing_tests(c),
    } for c in result.get("candidates", [])]
    slug = plan["issue"].removeprefix("https://github.com/").replace("/issues/", "#")
    return {
        "issue": slug, "url": plan["issue"], "title": plan["title"], "run": name[:8],
        "commit": report["setup"]["commit"], "max_steps": plan["config"]["max_steps"],
        "tokens": spend["prompt_tokens"] + spend["completion_tokens"], "sandbox_runs": spend["sandbox_spawns"],
        "selected": result.get("selected"), "proven": bool(result.get("proven")), "candidates": candidates,
        "review": REVIEWED_NOT_A_FIX.get(plan["issue"]),
        "clean": plan["issue"] not in REVIEWED_NOT_A_FIX and any(c["id"] == result.get("selected") and c["proven"] and not c["regressions"] for c in candidates),
        "note": ANNOTATIONS.get(plan["issue"]),
    }


def export_real_issues(reports: Path = REPORTS / "fix", out: Path = FIX_OUTPUT) -> int:
    """Newest finished run per issue (runs that failed setup have no result and are skipped)."""
    newest: dict[str, tuple[str, dict]] = {}
    for path in sorted(reports.glob("*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("result") is not None:
            newest[report["plan"]["issue"]] = (path.name, report)
    issues = [export_issue(report, name) for name, report in newest.values()]
    if not issues:
        return 0
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "issues": len(issues),
        "proven": sum(i["proven"] for i in issues),
        "clean": sum(i["clean"] for i in issues),
        "patched": sum(bool(i["candidates"]) for i in issues),
        "tokens": sum(i["tokens"] for i in issues),
        "rows": issues,
    }
    (out / "index.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    return len(issues)


def fork_points(mode: dict) -> int:
    return sum(n["stop"] == "branched" for n in mode["nodes"])


def main(args: argparse.Namespace) -> None:
    if args.real_issues_only:
        print(f"wrote {export_real_issues()} real-issue runs to {FIX_OUTPUT}")
        return
    tasks_files = [Path(p) for p in args.tasks_file] if args.tasks_file else [BENCHMARK_FILE]
    tasks, records, sources = [], {}, []
    for tasks_file in tasks_files:
        benchmark = json.loads(tasks_file.read_text(encoding="utf-8"))
        if len(set(benchmark["tasks"])) != len(benchmark["tasks"]) or set(tasks) & set(benchmark["tasks"]):
            raise SystemExit("task lists must contain unique, non-overlapping tasks")
        records.update(latest_reports(REPORTS / "day2", benchmark["tasks"], benchmark["created"]))
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
    print(f"wrote {export_real_issues()} real-issue runs to {FIX_OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-file", nargs="+",
                        help="one or more non-overlapping task lists (default: benchmark_tasks.json)")
    parser.add_argument("--real-issues-only", action="store_true", help="export only the forkfix.fix runs")
    main(parser.parse_args())
