"""Fix a real public GitHub issue: branch over sandbox snapshots, keep the fix a reproduction test proves.

Spends Token Factory and Sandbox credit only with --approve; without it, fetches the issue
(a free read of a public URL), prints the plan and exits. Evidence goes to ignored reports/fix/.

    .\\.venv\\Scripts\\python.exe -m forkfix.fix https://github.com/owner/repo/issues/1
    .\\.venv\\Scripts\\python.exe -m forkfix.fix https://github.com/owner/repo/issues/1 --setup-only --approve
    .\\.venv\\Scripts\\python.exe -m forkfix.fix https://github.com/owner/repo/issues/1 --approve
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from .agent import REPRO_PATH, TokenFactoryAgent
from .config import agent_model, judge_model, sandboxes, token_factory
from .judge import TokenFactoryJudge
from .repo import BASE_IMAGE, MAX_ISSUE_CHARS, RepoError, SETUP_TIMEOUT, SetupResult, fetch_issue, parse_issue_url, parse_setup, real_task, setup_script
from .run_day2 import _tree, save
from .search import Search, SearchConfig
from .tasks import Task
from .verify import Verifier
from .workspace import Meter, SandboxWorkspace, Workspace, with_retries


async def build_base(ref, commit: str, meter: Meter) -> tuple[Workspace | None, SetupResult]:
    """Import the base image and run the setup script; the returned workspace is the fork point."""
    client = sandboxes()
    image = SandboxWorkspace(await with_retries(lambda: client.images.oci(BASE_IMAGE), attempts=5, delay=10))
    workspace, result = await image.run(setup_script(ref, commit), meter=meter, timeout=SETUP_TIMEOUT)
    setup = parse_setup(result.output)
    return (workspace if setup.ok else None), setup


async def solve(task: Task, base: Workspace, config: SearchConfig, budget: Meter) -> dict:
    """Branching search on one real task; selection prefers fixes proven by their own reproduction test."""
    meter = budget.child()
    agent = TokenFactoryAgent(token_factory(), agent_model())
    judge = TokenFactoryJudge(token_factory(), judge_model())
    result = await Search(task, agent, judge, config, meter, Verifier(task, base)).run(base)
    selected = result.selected
    return {
        "selected": selected.id if selected else None,
        "proven": bool(selected and selected.repro and selected.repro.ok),
        "rounds": result.rounds,
        "candidates": [{
            "id": c.id, "stop_reason": c.stop_reason, "steps": c.steps, "judge_score": c.score,
            "reproduction": c.repro.summary() if c.repro else None,
            "reproduction_ok": bool(c.repro and c.repro.ok),
            "existing_tests": c.check.summary() if c.check else None,
            "patch": c.patch,
        } for c in result.candidates],
        "tree": _tree(result.all_trajectories),
        "spend": meter.summary(),
    }


async def main(args: argparse.Namespace) -> None:
    ref = parse_issue_url(args.issue_url)
    if args.issue_file:
        data = json.loads(Path(args.issue_file).read_text(encoding="utf-8"))
        title, body = data["title"], data.get("body", "")[:MAX_ISSUE_CHARS]
    else:
        title, body = fetch_issue(ref)
    config = SearchConfig(width=args.width, branch_factor=args.branch, max_steps=args.max_steps)
    plan = {"issue": args.issue_url, "title": title, "commit": args.commit or "default branch head",
            "setup_only": args.setup_only, "agent_model": agent_model(), "judge_model": judge_model(),
            "config": asdict(config), "max_tokens": args.max_tokens, "max_spawns": args.max_spawns,
            "reproduction_file": REPRO_PATH}
    print(json.dumps(plan, indent=2))
    if not args.approve:
        print("Dry run: nothing was spent. Add --approve to run.")
        return

    budget = Meter(max_tokens=args.max_tokens, max_spawns=args.max_spawns)
    base, setup = await build_base(ref, args.commit, budget.child(enforce=False))
    record: dict = {"plan": plan, "setup": asdict(setup)}
    print(setup.summary())
    if base is not None and not args.setup_only:
        task = real_task(ref, title, body, setup.commit)
        record["result"] = await solve(task, base, config, budget)
        chosen = record["result"]["selected"]
        print(f"selected: {chosen}, proven by its reproduction test: {record['result']['proven']}")
    record["total_spend"] = budget.summary()
    print("saved", save(f"{ref.owner}__{ref.repo}-{ref.number}", record, "fix"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("issue_url", help="public issue, e.g. https://github.com/owner/repo/issues/123")
    parser.add_argument("--issue-file", help='JSON {"title", "body"} instead of fetching from GitHub')
    parser.add_argument("--commit", default="", help="hex sha to pin; default is the head of the default branch")
    parser.add_argument("--width", type=int, default=4)
    parser.add_argument("--branch", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=50, help="real issues need more than SWE-bench's 30")
    parser.add_argument("--max-tokens", type=int, default=5_000_000, help="hard cap for this issue")
    parser.add_argument("--max-spawns", type=int, default=600)
    parser.add_argument("--setup-only", action="store_true", help="build the environment, run no model")
    parser.add_argument("--approve", action="store_true", help="actually spend credits")
    try:
        asyncio.run(main(parser.parse_args()))
    except RepoError as error:
        raise SystemExit(str(error))
