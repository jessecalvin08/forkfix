"""Review-and-approval records that bind a human decision to one exact policy.

The dashboard can approve a policy but never runs anything. An approval is a
JSON record in the git-ignored ``reports/approvals/`` directory, named by the
SHA-256 of the policy's canonical JSON. The Sandbox CLI accepts that ID, and
re-derives the hash and re-runs the local check matrix before it spends anything,
so an edited, swapped, or no-longer-passing policy is refused rather than run.

Evidence written by the CLI lands in ``reports/evidence/`` and is only ever
read back here, never produced by the API.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .models import Policy, PolicyValidationResponse
from .policy_validation import validate_policy
from .sandbox_runner import SandboxComparison


REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
APPROVAL_ID = re.compile(r"[0-9a-f]{64}")
MAX_RULES = 60


class ApprovalError(ValueError):
    """An approval is missing, malformed, or no longer matches its policy."""


class PolicyNotApprovable(ValueError):
    """The policy failed the local matrix, so it cannot be approved."""

    def __init__(self, validation: PolicyValidationResponse):
        super().__init__(validation.message)
        self.validation = validation


class ApprovalRecord(BaseModel):
    approval_id: str
    policy_sha256: str
    approved_at: datetime
    checks_passed: int
    checks_total: int
    policy: Policy
    cli_command: str


class EvidenceItem(BaseModel):
    file: str
    evidence: SandboxComparison


def approvals_dir() -> Path:
    return REPORTS_DIR / "approvals"


def evidence_dir() -> Path:
    return REPORTS_DIR / "evidence"


def policy_digest(policy: Policy) -> str:
    """Hash the policy's canonical JSON; rule order is kept because it is the author's."""
    canonical = json.dumps(policy.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cli_command(approval_id: str) -> str:
    return f".\\.venv\\Scripts\\python.exe -m app.run_sandbox --approval {approval_id} --approve"


def approve_policy(policy: Policy) -> ApprovalRecord:
    """Record an approval only for a policy that passes the matrix on the server."""
    if len(policy.rules) > MAX_RULES:
        raise ApprovalError(f"A policy with more than {MAX_RULES} rules cannot be approved here.")
    validation = validate_policy(policy)
    if not validation.passed:
        raise PolicyNotApprovable(validation)
    digest = policy_digest(policy)
    record = ApprovalRecord(
        approval_id=digest,
        policy_sha256=digest,
        approved_at=datetime.now(timezone.utc),
        checks_passed=validation.passed_checks,
        checks_total=validation.total_checks,
        policy=policy,
        cli_command=cli_command(digest),
    )
    directory = approvals_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{digest}.json"
    staging = target.with_suffix(".json.tmp")
    staging.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    staging.replace(target)
    return record


def load_approval(approval_id: str) -> ApprovalRecord:
    """Load an approval and prove it still describes an approvable policy."""
    if not APPROVAL_ID.fullmatch(approval_id):
        raise ApprovalError("An approval ID is the 64-character lowercase SHA-256 shown in the dashboard.")
    path = approvals_dir() / f"{approval_id}.json"
    if not path.is_file():
        raise ApprovalError("No approval with that ID exists in reports/approvals/.")
    try:
        record = ApprovalRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise ApprovalError("The approval record is malformed.") from error
    if record.approval_id != approval_id or record.policy_sha256 != approval_id:
        raise ApprovalError("The approval record does not match its own ID.")
    if policy_digest(record.policy) != approval_id:
        raise ApprovalError("The policy in this approval was changed after it was approved.")
    if not validate_policy(record.policy).passed:
        raise ApprovalError("The approved policy no longer passes the local check matrix.")
    return record


def list_approvals() -> list[ApprovalRecord]:
    """Newest first; a record that fails verification is left out, not shown as approved."""
    directory = approvals_dir()
    if not directory.is_dir():
        return []
    records = []
    for path in directory.glob("*.json"):
        try:
            records.append(load_approval(path.stem))
        except ApprovalError:
            continue
    return sorted(records, key=lambda record: record.approved_at, reverse=True)


def list_evidence() -> list[EvidenceItem]:
    """Newest first. Only files that validate as a Sandbox comparison are returned."""
    directory = evidence_dir()
    if not directory.is_dir():
        return []
    items = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            evidence = SandboxComparison.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, UnicodeDecodeError, OSError):
            continue
        items.append(EvidenceItem(file=path.name, evidence=evidence))
    return items
