from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"
    VIOLATION = "violation"


class RuleEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class PolicyRule(BaseModel):
    id: str
    effect: RuleEffect
    tool: str
    path_patterns: list[str] = Field(default_factory=lambda: ["**"])
    reason: str = ""


class Policy(BaseModel):
    version: str = "1"
    rules: list[PolicyRule]


class ToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    sequence: int
    tool: str
    arguments: dict[str, Any]
    decision: Decision
    rule_id: str | None = None
    summary: str


class RunMetrics(BaseModel):
    unauthorized_attempts: int
    blocked_actions: int
    benign_task_completed: bool
    policy_verdict: str


class DemoRun(BaseModel):
    id: str
    label: str
    enforcement_mode: str
    trace: list[TraceEvent]
    metrics: RunMetrics


class DemoComparison(BaseModel):
    policy: Policy
    baseline: DemoRun
    repair: DemoRun
    finding: str
    repair_summary: str


class PolicyCompileRequest(BaseModel):
    policy_text: str = Field(min_length=10, max_length=4000)


class NebiusConnectionStatus(BaseModel):
    configured: bool
    connected: bool
    message: str
    model_count: int = 0
    nvidia_model_candidates: list[str] = Field(default_factory=list)
    recommended_model: str | None = None


class PolicyCompileResponse(BaseModel):
    status: Literal["compiled"]
    message: str
    model: str
    response_mode: Literal["json_schema", "json_object"]
    policy: Policy


class PolicyValidationRequest(BaseModel):
    policy: Policy


class PolicyApprovalRequest(BaseModel):
    """`reviewed` must be literally true: approval is a deliberate human act, not a default."""

    policy: Policy
    reviewed: Literal[True]


class PolicyValidationCase(BaseModel):
    id: str
    label: str
    category: Literal["allowed_work", "boundary"]
    expected: Decision
    actual: Decision
    passed: bool
    rule_id: str | None = None


class PolicyValidationResponse(BaseModel):
    status: Literal["passed", "failed"]
    passed: bool
    passed_checks: int
    total_checks: int
    message: str
    cases: list[PolicyValidationCase]
