import type {
  ApprovalRecord,
  DemoComparison,
  EvidenceItem,
  NebiusConnectionStatus,
  Policy,
  PolicyCompileResponse,
  PolicyValidationResponse,
} from "./types";

// Leave this unset for the safe, public static demo. Local development uses Vite's
// /api proxy; a deployed API can be explicitly supplied at build time instead.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

export const hasLiveApi = Boolean(API_BASE_URL) ||
  window.location.hostname === "127.0.0.1" ||
  window.location.hostname === "localhost";

function requireLiveApi(): void {
  if (!hasLiveApi) {
    throw new Error("This public demo intentionally uses a scripted fixture. Run RuleBranch locally to use Token Factory or compile a policy.");
  }
}

export async function fetchDemoComparison(): Promise<DemoComparison> {
  requireLiveApi();
  const response = await fetch(`${API_BASE_URL}/api/demo/comparison`);
  if (!response.ok) {
    throw new Error("The local RuleBranch API is unavailable.");
  }
  return (await response.json()) as DemoComparison;
}

export async function fetchNebiusConnectionStatus(): Promise<NebiusConnectionStatus> {
  requireLiveApi();
  const response = await fetch(`${API_BASE_URL}/api/nebius/status`);
  if (!response.ok) {
    throw new Error("RuleBranch could not check Token Factory.");
  }
  return (await response.json()) as NebiusConnectionStatus;
}

export async function compilePolicyWithNebius(policyText: string): Promise<PolicyCompileResponse> {
  requireLiveApi();
  const response = await fetch(`${API_BASE_URL}/api/policies/compile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ policy_text: policyText }),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "Token Factory could not compile the policy.");
  }
  return (await response.json()) as PolicyCompileResponse;
}

export async function validatePolicyDraft(policy: Policy): Promise<PolicyValidationResponse> {
  requireLiveApi();
  const response = await fetch(`${API_BASE_URL}/api/policies/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ policy }),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "RuleBranch could not test the generated draft.");
  }
  return (await response.json()) as PolicyValidationResponse;
}

/** FastAPI details are a string, or an object with a message for structured refusals. */
async function errorDetail(response: Response, fallback: string): Promise<string> {
  const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  if (response.status === 422) return "The server did not accept the approval. Check that the policy passes all 18 checks.";
  return fallback;
}

export async function approvePolicy(policy: Policy): Promise<ApprovalRecord> {
  requireLiveApi();
  const response = await fetch(`${API_BASE_URL}/api/policies/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ policy, reviewed: true }),
  });
  if (!response.ok) throw new Error(await errorDetail(response, "RuleBranch could not record the approval."));
  return (await response.json()) as ApprovalRecord;
}

export async function fetchEvidence(): Promise<EvidenceItem[]> {
  requireLiveApi();
  const response = await fetch(`${API_BASE_URL}/api/evidence`);
  if (!response.ok) throw new Error("RuleBranch could not read the Sandbox evidence folder.");
  return (await response.json()) as EvidenceItem[];
}
