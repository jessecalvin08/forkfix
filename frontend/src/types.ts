export type Decision = "allow" | "deny" | "approval_required" | "violation";

export interface PolicyRule {
  id: string;
  effect: "allow" | "deny" | "approval_required";
  tool: string;
  path_patterns: string[];
  reason: string;
}

export interface Policy {
  version: string;
  rules: PolicyRule[];
}

export interface TraceEvent {
  sequence: number;
  tool: string;
  arguments: Record<string, string>;
  decision: Decision;
  rule_id: string | null;
  summary: string;
}

export interface RunMetrics {
  unauthorized_attempts: number;
  blocked_actions: number;
  benign_task_completed: boolean;
  policy_verdict: string;
}

export interface DemoRun {
  id: string;
  label: string;
  enforcement_mode: string;
  trace: TraceEvent[];
  metrics: RunMetrics;
}

export interface DemoComparison {
  policy: Policy;
  baseline: DemoRun;
  repair: DemoRun;
  finding: string;
  repair_summary: string;
}

export interface NebiusConnectionStatus {
  configured: boolean;
  connected: boolean;
  message: string;
  model_count: number;
  nvidia_model_candidates: string[];
  recommended_model: string | null;
}

export interface PolicyCompileResponse {
  status: "compiled";
  message: string;
  model: string;
  response_mode: "json_schema" | "json_object";
  policy: Policy;
}

export interface PolicyValidationCase {
  id: string;
  label: string;
  category: "allowed_work" | "boundary";
  expected: Exclude<Decision, "violation">;
  actual: Exclude<Decision, "violation">;
  passed: boolean;
  rule_id: string | null;
}

export interface PolicyValidationResponse {
  status: "passed" | "failed";
  passed: boolean;
  passed_checks: number;
  total_checks: number;
  message: string;
  cases: PolicyValidationCase[];
}

export interface ApprovalRecord {
  approval_id: string;
  policy_sha256: string;
  approved_at: string;
  checks_passed: number;
  checks_total: number;
  policy: Policy;
  cli_command: string;
}

export interface RecordedAction {
  step: number;
  tool: string;
  target: string;
  policy_decision: Exclude<Decision, "violation">;
  executed: boolean;
  rule_id: string | null;
  result: string;
}

export interface BranchResult {
  mode: "observe" | "enforce";
  model: string;
  sandbox_image_id: string;
  events: RecordedAction[];
  tests_passed: boolean;
  test_exit_code: number;
  unauthorized_attempts: number;
  blocked_actions: number;
  safety_suppressed_actions: number;
}

export interface SandboxComparison {
  evidence_type: "nebius_sandbox_execution";
  fixture: string;
  policy_sha256: string | null;
  approval_id: string | null;
  recorded_at: string | null;
  observe: BranchResult;
  enforce: BranchResult;
}

export interface EvidenceItem {
  file: string;
  evidence: SandboxComparison;
}
