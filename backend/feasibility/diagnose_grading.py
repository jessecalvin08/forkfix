"""Inspect one SWE-bench grading run without exposing tests to an agent."""

from __future__ import annotations

import argparse
import asyncio
import json

from forkfix.config import sandboxes
from forkfix.tasks import grading_script, load_tasks, parse_pytest_report
from forkfix.workspace import Meter, SandboxWorkspace


async def main(instance_id: str) -> None:
    task = next(t for t in load_tasks(pytest_only=False) if t.instance_id == instance_id)
    client = sandboxes()
    base = SandboxWorkspace(await client.images.oci(task.image))
    gold, applied = await base.run(
        "cd /testbed && git apply /tmp/forkfix_gold.patch",
        files={"/tmp/forkfix_gold.patch": task.gold_patch.encode()},
        meter=Meter(), timeout=120,
    )
    workspace = gold if applied.exit_code == 0 else base
    _, result = await workspace.run(
        grading_script(task),
        files={"/tmp/forkfix_test.patch": task.test_patch.encode()},
        meter=Meter(), timeout=900,
    )
    statuses = parse_pytest_report(result.output)
    required = task.fail_to_pass + task.pass_to_pass
    missing = [test for test in required if test not in statuses]
    not_passing = {test: statuses[test] for test in required if test in statuses and statuses[test] not in ("PASSED", "XFAIL")}
    print(json.dumps({
        "instance_id": instance_id,
        "gold_applied": applied.exit_code == 0,
        "grader_exit_code": result.exit_code,
        "required_tests": len(required),
        "reported_tests": len(statuses),
        "missing": missing,
        "not_passing": not_passing,
        "output_tail": result.output[-3000:],
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("instance_id")
    asyncio.run(main(parser.parse_args().instance_id))
