"""Feasibility check 2 (paid): can Nebius Sandboxes run a real SWE-bench Lite task?

Imports the task's official prebuilt SWE-bench image from Docker Hub, then from
that one snapshot runs two forks:
  * unfixed: apply the hidden test patch, run FAIL_TO_PASS -> must FAIL
  * gold:    apply the reference fix + test patch, run FAIL_TO_PASS -> must PASS
If both hold, the evaluation loop the tree-search agent needs works end to end.
Records import time, run times, and the per-run cost the Sandbox API reports.

    .\\.venv\\Scripts\\python.exe -m feasibility.probe_swebench --instance pytest-dev__pytest-7373
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import time
import urllib.request

from ._common import RAW, REPORTS, sandbox_async, save_report, text

DATASET = "princeton-nlp/SWE-bench_Lite"
ROWS_URL = "https://datasets-server.huggingface.co/rows?dataset={ds}&config=default&split=test&offset={off}&length=100"
CACHE = REPORTS / "swe_bench_lite.json"


def load_instances() -> dict[str, dict]:
    """The 300 public SWE-bench Lite rows, cached locally after the first fetch."""
    if not CACHE.exists():
        rows = []
        for offset in range(0, 300, 100):
            with urllib.request.urlopen(ROWS_URL.format(ds=DATASET, off=offset), timeout=60) as response:
                rows += [r["row"] for r in json.load(response)["rows"]]
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(rows), encoding="utf-8")
    return {row["instance_id"]: row for row in json.loads(CACHE.read_text(encoding="utf-8"))}


def image_ref(instance_id: str) -> str:
    # SWE-bench's Docker Hub naming: "__" becomes "_1776_", lower-cased.
    return f"swebench/sweb.eval.x86_64.{instance_id.lower().replace('__', '_1776_')}:latest"


def test_script(fail_to_pass: list[str], apply_gold: bool) -> str:
    steps = ["source /opt/miniconda3/bin/activate testbed", "cd /testbed"]
    if apply_gold:
        steps.append("git apply /tmp/gold.patch")
    steps.append("git apply /tmp/test.patch")
    steps.append("python -m pytest -q -p no:cacheprovider " + " ".join(shlex.quote(t) for t in fail_to_pass))
    return " && ".join(steps)


async def main(instance_id: str) -> None:
    task = load_instances()[instance_id]
    fail_to_pass = json.loads(task["FAIL_TO_PASS"])
    client = sandbox_async()

    t0 = time.monotonic()
    image = await client.images.oci(image_ref(instance_id))
    import_seconds = time.monotonic() - t0

    patches = {"/tmp/test.patch": task["test_patch"].encode(), "/tmp/gold.patch": task["patch"].encode()}

    async def evaluate(apply_gold: bool):
        started = time.monotonic()
        result = await image.run(
            command="bash", args=["-lc", test_script(fail_to_pass, apply_gold)],
            files=patches, timeout=900, truncate_output_at=4000, **RAW,
        )
        return result, time.monotonic() - started

    (unfixed, unfixed_s), (gold, gold_s) = await asyncio.gather(evaluate(False), evaluate(True))

    report = {
        "instance_id": instance_id,
        "image": image_ref(instance_id),
        "import_seconds": round(import_seconds, 1),
        "unfixed_exit_code": unfixed.exit_code,
        "gold_exit_code": gold.exit_code,
        "harness_ok": unfixed.exit_code != 0 and gold.exit_code == 0,
        "unfixed_seconds": round(unfixed_s, 1),
        "gold_seconds": round(gold_s, 1),
        "reported_cost": {"unfixed": unfixed.result.cost, "gold": gold.result.cost},
        "gold_tail": text(gold.stdout)[-600:],
        "unfixed_tail": text(unfixed.stdout)[-600:],
    }
    print(json.dumps(report, indent=2))
    print("saved", save_report(f"probe_swebench-{instance_id}", report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", default="pytest-dev__pytest-7373")
    asyncio.run(main(parser.parse_args().instance))
