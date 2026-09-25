"""Feasibility check 1 (paid, tiny): can we fork sandbox state and run branches in parallel?

Builds one snapshot, forks it N ways concurrently, and checks that:
  * every child sees the parent's state plus only its own change (isolation),
  * a grandchild inherits its parent's change (depth works),
  * the parent snapshot is unchanged afterwards (immutability),
and records wall-clock time against the summed run time (real parallelism) plus
the per-run ``cost`` the Sandbox API reports.

    .\\.venv\\Scripts\\python.exe -m feasibility.probe_fork --branches 16
"""

from __future__ import annotations

import argparse
import asyncio
import time

from ._common import RAW, sandbox_async, save_report, text

BASE_IMAGE = "python:3.11"


async def main(branches: int) -> None:
    client = sandbox_async()
    t0 = time.monotonic()
    base = await client.images.use(BASE_IMAGE)
    root = await base.run(
        shell="mkdir -p /w && echo root > /w/log", disposable=False, timeout=120, **RAW,
    )
    root_seconds = time.monotonic() - t0
    assert root.exit_code == 0, text(root.stderr)

    async def child(i: int):
        started = time.monotonic()
        # sleep 5 makes parallelism measurable: serial would take >= 5 * branches seconds.
        result = await root.run(
            shell=f"echo {i} >> /w/log && sleep 5 && cat /w/log", disposable=False, timeout=120, **RAW,
        )
        return i, result, time.monotonic() - started

    t1 = time.monotonic()
    children = await asyncio.gather(*(child(i) for i in range(branches)))
    fan_out_wall = time.monotonic() - t1

    isolated = [text(r.stdout).split() == ["root", str(i)] for i, r, _ in children]

    first = children[0][1]
    grandchild = await first.run(shell="echo g >> /w/log && cat /w/log", disposable=False, timeout=60, **RAW)
    depth_ok = text(grandchild.stdout).split() == ["root", "0", "g"]

    parent_after = await root.run(shell="cat /w/log", timeout=60, **RAW)
    immutable = text(parent_after.stdout).split() == ["root"]

    per_run = [secs for _, _, secs in children]
    costs = [r.result.cost for _, r, _ in children] + [root.result.cost, grandchild.result.cost, parent_after.result.cost]
    report = {
        "branches": branches,
        "root_snapshot_seconds": round(root_seconds, 1),
        "fan_out_wall_seconds": round(fan_out_wall, 1),
        "per_branch_seconds_min_max": [round(min(per_run), 1), round(max(per_run), 1)],
        "serial_lower_bound_seconds": 5 * branches,
        "isolation_ok": all(isolated),
        "isolation_failures": [i for i, ok in enumerate(isolated) if not ok],
        "depth_ok": depth_ok,
        "parent_immutable": immutable,
        "reported_cost_total": sum(costs),
        "reported_cost_per_branch": [r.result.cost for _, r, _ in children],
    }
    print(report)
    print("saved", save_report("probe_fork", report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--branches", type=int, default=16)
    asyncio.run(main(parser.parse_args().branches))
