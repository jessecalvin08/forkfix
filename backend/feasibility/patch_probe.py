"""Sandbox-only check (no model calls): run a probe script on a real-issue repository before and after a saved patch.

    python -m feasibility.patch_probe --report reports/fix/<file>.json --candidate 0.2.0.0 --probe probe.py --approve

Sets up the repository exactly as forkfix.fix does, runs the probe, applies the candidate's patch, and runs it again.
Prints both outputs so a human can see what the patch changes on inputs the agent's own test never tried."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from forkfix.fix import build_base
from forkfix.repo import REAL_ACTIVATE, parse_issue_url
from forkfix.workspace import Meter

PATCH_PATH, PROBE_PATH = "/tmp/candidate.patch", "/tmp/probe.py"


async def main(args: argparse.Namespace) -> None:
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    candidate = next(c for c in report["result"]["candidates"] if c["id"] == args.candidate)
    ref = parse_issue_url(report["plan"]["issue"])
    plan = f"{ref.owner}/{ref.repo} @ {report['setup']['commit'][:10]}, candidate {args.candidate}, probe {args.probe}"
    if not args.approve:
        print(f"Dry run ({plan}). Uses Sandbox runs only, no model. Add --approve to run.")
        return
    meter = Meter(max_spawns=60)
    base, setup = await build_base(ref, report["setup"]["commit"], meter)
    if base is None:
        raise SystemExit(f"setup failed: {setup.message}")
    probe = Path(args.probe).read_bytes()
    run = f"cd /testbed && {REAL_ACTIVATE} && python {PROBE_PATH} 2>&1"
    _, before = await base.run(run, files={PROBE_PATH: probe}, meter=meter, timeout=300)
    patched, applied = await base.run(
        f"cd /testbed && git apply {PATCH_PATH} && echo applied", files={PATCH_PATH: candidate["patch"].encode()},
        meter=meter, timeout=120)
    print(f"== {plan}\n== patch: {applied.output.strip()[-80:]}")
    _, after = await patched.run(run, files={PROBE_PATH: probe}, meter=meter, timeout=300)
    print("---- BEFORE (unpatched) ----\n" + before.output.strip())
    print("---- AFTER (patched) ----\n" + after.output.strip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--probe", required=True)
    parser.add_argument("--approve", action="store_true", help="actually use Sandbox runs")
    asyncio.run(main(parser.parse_args()))
