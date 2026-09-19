"""Explicit CLI approval gate for the Nebius Sandbox comparison.

From backend/, run a policy approved in the dashboard:
    python -m app.run_sandbox --approval <64-char id> --approve
or a policy file you reviewed by hand:
    python -m app.run_sandbox --reviewed-policy policy.json --approve

Either way the run is refused without --approve. An approval is re-verified
(hash and local check matrix) before anything is spent, and its evidence is written
to reports/evidence/ where the dashboard can read it back.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .approvals import ApprovalError, evidence_dir, load_approval, policy_digest
from .attack_generation import generate_attack_scenario
from .attack_scenarios import SCENARIOS_BY_ID, get_scenario
from .models import Policy
from .sandbox_runner import run_sandbox_comparison


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the synthetic RuleBranch fixture in Nebius Sandboxes")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--approval", help="ID of a policy approved in the dashboard (reports/approvals/<id>.json)")
    source.add_argument("--reviewed-policy", type=Path, help="Path to a policy JSON you reviewed")
    parser.add_argument("--approve", action="store_true", help="Explicitly authorize this opt-in paid API/Sandbox run")
    parser.add_argument("--output", type=Path, help="Evidence output path; defaults to reports/evidence/ for approvals")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS_BY_ID), help="Hand-written attack scenario to inject (default: quoted-note)")
    parser.add_argument("--generate-attack", action="store_true", help="Ask Nemotron to write a fresh injection (paid) and run that instead")
    parser.add_argument("--attack-hint", help="Optional angle to steer --generate-attack")
    args = parser.parse_args(argv)
    if not args.approve:
        parser.error("Review the policy and pass --approve to authorize the run.")
    if args.generate_attack and args.scenario:
        parser.error("Choose either --scenario or --generate-attack, not both.")

    approval_id = None
    if args.approval:
        try:
            record = load_approval(args.approval)
        except ApprovalError as error:
            parser.error(f"Approval refused: {error}")
        policy, approval_id = record.policy, record.approval_id
    else:
        policy = Policy.model_validate_json(args.reviewed_policy.read_text(encoding="utf-8"))

    if args.generate_attack:
        try:
            scenario = generate_attack_scenario(args.attack_hint)
        except ValueError as error:
            parser.error(f"Attack generation failed: {error}")
        print(json.dumps({"generated_scenario": scenario.id, "label": scenario.label, "technique": scenario.technique}))
    else:
        scenario = get_scenario(args.scenario)
    recorded_at = datetime.now(timezone.utc)
    digest = policy_digest(policy)
    result = run_sandbox_comparison(policy, scenario).model_copy(
        update={"policy_sha256": digest, "approval_id": approval_id, "recorded_at": recorded_at}
    )
    rendered = result.model_dump_json(indent=2)

    output = args.output
    if output is None and approval_id:
        output = evidence_dir() / f"{recorded_at:%Y%m%dT%H%M%SZ}-{scenario.id}-{digest[:12]}.json"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        print(json.dumps({"evidence_type": result.evidence_type, "output": str(output)}))
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
