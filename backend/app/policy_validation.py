from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import (
    Decision,
    Policy,
    PolicyValidationCase,
    PolicyValidationResponse,
    ToolCall,
)
from .policy_engine import evaluate


@dataclass(frozen=True)
class ValidationFixture:
    id: str
    label: str
    category: Literal["allowed_work", "boundary"]
    call: ToolCall
    expected: Decision
    # Decisions that also satisfy the intended authority. Deleting is the one
    # case with two safe answers: refuse outright, or stop for a human.
    also_accepted: tuple[Decision, ...] = ()


VALIDATION_FIXTURES = (
    ValidationFixture("read-readme", "Read README.md", "allowed_work", ToolCall(tool="read_file", arguments={"path": "README.md"}), Decision.ALLOW),
    ValidationFixture("read-source", "Read a source file", "allowed_work", ToolCall(tool="read_file", arguments={"path": "src/app.py"}), Decision.ALLOW),
    ValidationFixture("read-tests", "Read a test file", "allowed_work", ToolCall(tool="read_file", arguments={"path": "tests/test_app.py"}), Decision.ALLOW),
    ValidationFixture("write-source", "Write inside src/", "allowed_work", ToolCall(tool="write_file", arguments={"path": "src/app.py"}), Decision.ALLOW),
    ValidationFixture("run-pytest", "Run the exact pytest capability", "allowed_work", ToolCall(tool="run_tests", arguments={"path": "pytest"}), Decision.ALLOW),
    ValidationFixture("root-env", "Block root .env", "boundary", ToolCall(tool="read_file", arguments={"path": ".env"}), Decision.DENY),
    ValidationFixture("nested-env", "Block nested .env", "boundary", ToolCall(tool="read_file", arguments={"path": "src/.env"}), Decision.DENY),
    ValidationFixture("root-git", "Block root Git metadata", "boundary", ToolCall(tool="read_file", arguments={"path": ".git/config"}), Decision.DENY),
    ValidationFixture("nested-git", "Block nested Git metadata", "boundary", ToolCall(tool="read_file", arguments={"path": "src/.git/config"}), Decision.DENY),
    ValidationFixture("private-key", "Block private-key files", "boundary", ToolCall(tool="read_file", arguments={"path": "src/private.pem"}), Decision.DENY),
    ValidationFixture("network", "Block network requests", "boundary", ToolCall(tool="http_request", arguments={"url": "https://example.invalid/collect"}), Decision.DENY),
    ValidationFixture("delete", "Block file deletion", "boundary", ToolCall(tool="delete_file", arguments={"path": "src/app.py"}), Decision.DENY, (Decision.APPROVAL_REQUIRED,)),
    ValidationFixture("outside-write", "Block writes outside src/", "boundary", ToolCall(tool="write_file", arguments={"path": "README.md"}), Decision.DENY),
    ValidationFixture("write-traversal", "Block source path traversal", "boundary", ToolCall(tool="write_file", arguments={"path": "src/../README.md"}), Decision.DENY),
    ValidationFixture("read-traversal", "Block secret path traversal", "boundary", ToolCall(tool="read_file", arguments={"path": "src/../.env"}), Decision.DENY),
    ValidationFixture("other-test", "Block any test target except pytest", "boundary", ToolCall(tool="run_tests", arguments={"path": "unapproved-test-target"}), Decision.DENY),
    ValidationFixture("missing-target", "Block a test call without a target", "boundary", ToolCall(tool="run_tests", arguments={}), Decision.DENY),
    ValidationFixture("write-env", "Block writing .env", "boundary", ToolCall(tool="write_file", arguments={"path": ".env"}), Decision.DENY),
    ValidationFixture("write-git", "Block writing Git hooks", "boundary", ToolCall(tool="write_file", arguments={"path": ".git/hooks/pre-commit"}), Decision.DENY),
    ValidationFixture("env-variant", "Block .env.local and similar variants", "boundary", ToolCall(tool="read_file", arguments={"path": ".env.local"}), Decision.DENY),
    ValidationFixture("ssh-key", "Block SSH private keys", "boundary", ToolCall(tool="read_file", arguments={"path": "src/id_rsa"}), Decision.DENY),
    ValidationFixture("case-variant", "Block secrets spelled in another case", "boundary", ToolCall(tool="read_file", arguments={"path": ".ENV"}), Decision.DENY),
    ValidationFixture("unknown-tool", "Block an unknown tool", "boundary", ToolCall(tool="shell", arguments={"path": "pytest"}), Decision.DENY),
)


def validate_policy(policy: Policy) -> PolicyValidationResponse:
    cases: list[PolicyValidationCase] = []
    for fixture in VALIDATION_FIXTURES:
        actual, rule = evaluate(policy, fixture.call)
        cases.append(
            PolicyValidationCase(
                id=fixture.id,
                label=fixture.label,
                category=fixture.category,
                expected=fixture.expected,
                actual=actual,
                passed=actual == fixture.expected or actual in fixture.also_accepted,
                rule_id=rule.id if rule else None,
            )
        )

    passed_checks = sum(case.passed for case in cases)
    passed = passed_checks == len(cases)
    message = (
        "All local synthetic checks matched the intended authority. No agent, command, file, or network action was executed."
        if passed
        else "One or more local synthetic checks disagreed with the intended authority. The draft remains unapproved and was not executed."
    )
    return PolicyValidationResponse(
        status="passed" if passed else "failed",
        passed=passed,
        passed_checks=passed_checks,
        total_checks=len(cases),
        message=message,
        cases=cases,
    )
