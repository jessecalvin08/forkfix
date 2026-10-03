"""Replay the saved real-issue runs against the agent changes made after they ran. Free: reads reports only.

Checks three changes against what the old agent actually did (it cannot show that they raise the fix rate,
only what they would have changed):
  * package installs are refused in real-issue mode (INSTALL_COMMAND),
  * judge scores of patches whose own reproduction test does not prove them are capped (UNPROVEN_CAP),
  * the step budget went from 30 to 50, so branches that ran out of steps get 20 more.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import INSTALL_COMMAND
from .judge import UNPROVEN_CAP

REPORTS = Path(__file__).resolve().parents[1] / "reports" / "fix"
OLD_MAX_STEPS = 30
EDIT_FAILURE = "matches 0 times"


def newest_per_issue(folder: Path) -> dict[str, dict]:
    newest: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("result") is not None:
            newest[report["plan"]["issue"]] = report
    return newest


def replay_issue(report: dict) -> dict:
    result = report["result"]
    events = [e for node in result["tree"] for e in node["events"]]
    installs = [e["summary"] for e in events if e["tool"] == "bash" and INSTALL_COMMAND.search(e["summary"])]
    edit_failures = sum(EDIT_FAILURE in (e.get("observation") or "") for e in events)
    out_of_steps = [n["id"] for n in result["tree"] if n["stop_reason"] == "step_limit"]
    candidates = []
    for c in result["candidates"]:
        score = c["judge_score"]
        capped = min(score, UNPROVEN_CAP) if score is not None and not c["reproduction_ok"] else score
        candidates.append({"id": c["id"], "judge": score, "capped": capped, "proven": bool(c["reproduction_ok"])})
    old_best = max(candidates, key=lambda c: -1 if c["judge"] is None else c["judge"], default=None)
    new_best = max(candidates, key=lambda c: -1 if c["capped"] is None else c["capped"], default=None)
    return {
        "issue": report["plan"]["issue"],
        "installs_now_refused": installs,
        "edit_failures_seen": edit_failures,
        "branches_out_of_steps": out_of_steps,
        "candidates": candidates,
        "best_judge_before": old_best and old_best["judge"],
        "best_judge_after": new_best and new_best["capped"],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reports", default=str(REPORTS))
    parser.add_argument("--json", action="store_true", help="print the full replay as JSON")
    args = parser.parse_args(argv)
    rows = [replay_issue(r) for r in newest_per_issue(Path(args.reports)).values()]
    if args.json:
        print(json.dumps(rows, indent=1))
        return
    print(f"{'issue':<34}{'installs':>9}{'edit fails':>11}{'out of steps':>13}{'patches':>8}{'best judge':>16}")
    for r in rows:
        judge = f"{r['best_judge_before']} -> {r['best_judge_after']}" if r["candidates"] else "-"
        print(f"{r['issue']:<34}{len(r['installs_now_refused']):>9}{r['edit_failures_seen']:>11}"
              f"{len(r['branches_out_of_steps']):>13}{len(r['candidates']):>8}{judge:>16}")
    print(f"\nTotals: {sum(len(r['installs_now_refused']) for r in rows)} install attempts now refused, "
          f"{sum(r['edit_failures_seen'] for r in rows)} 'matches 0 times' edit failures, "
          f"{sum(len(r['branches_out_of_steps']) for r in rows)} branches that hit the old {OLD_MAX_STEPS}-step limit.")


if __name__ == "__main__":
    main()
