# RuleBranch status

Last updated: September 19, 2026

## Current position

The local prototype has a verified live policy-generation call to NVIDIA Nemotron through Nebius Token Factory. A bounded Nebius Sandbox coding-agent runner is implemented, but it has not produced a live execution result yet. Sandbox access, blocked on September 18 (`spawn=false`, HTTP 403 for image listing), was confirmed granted on September 19 (`spawn=true`). The dashboard still shows only a scripted sample, not measured real agent behavior.

| Item | Status | Notes |
| --- | --- | --- |
| Devpost registration | Complete | Confirmation email received |
| Project direction | Complete | RuleBranch, Coding and Agentic Engineering track |
| Project workspace | Complete | Documentation, MIT license, git ignore rules, and implementation structure created |
| Token Factory credit request | Complete | Jesse redeemed the promo code and activated Token Factory |
| Token Factory account and credit redemption | Needs balance check | Dashboard is active; visible badge currently shows $1 trial, so confirm the separate promotional balance in Billing settings |
| API key | Stored locally | Jesse saved `rulebranch-local-dev` in ignored `backend/.env`; the key value was never shared or inspected |
| Token Factory connection check | Verified | Authenticated model listing works; listing models alone does not prove generation |
| Selected NVIDIA model | Configured and verified | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`; corrected a duplicated `NEBIUS_MODEL=` assignment without changing the key |
| JSON policy compiler | Live generation verified | Running API returned `status: compiled`, `response_mode: json_schema`, and 12 rules including 3 local guards on September 14 |
| Generated-policy semantics | Hardened, local checks added | Generated `run_tests` rules must allow exactly `pytest`; the evaluator rejects absolute/traversal paths and protects nested secret/Git paths. A fixed 23-case local matrix (18 originally; five added for protected writes, `.env.*` variants, key files and case-folding) now checks the generated draft against the demo's intended authority |
| Local policy evaluator | Unit-tested, simulation only | Checks scripted calls; does not execute a real coding agent, file edit, upload, or repository test |
| Generated-draft test | 18/18 passed, synthetic only | The exact 12-rule draft displayed in Jesse's RuleBranch tab was validated through the local API on September 14: all 5 permitted-operation checks and 13 prohibited/invalid-operation checks passed. No browser focus, Token Factory request, file action, command action, or network action was involved |
| React + FastAPI dashboard | Build passed | Generated drafts are separate from sample traces, edits mark drafts stale, failures are visibly errors, and generated drafts can be tested locally |
| Regression tests | 66 passed | Offline tests cover generation contracts, malformed output, reserved guards, path and test-runner enforcement, the 18-case matrix, API integration, secret-safe errors, the Sandbox runner's synthetic-only safety boundary, and the approval gate (hash binding, tamper refusal, ID traversal, CLI refusal before spend, evidence linkage); 2 dependency deprecation warnings |
| Review and approval flow | Implemented, tested locally | The dashboard runs the local checks (23) on the policy on screen, requires an explicit "I have read every rule" acknowledgement, and the server re-runs the matrix before writing an approval to ignored `reports/approvals/<sha256>.json`. `run_sandbox --approval <id> --approve` re-derives the hash and re-runs the matrix before any spend, so an edited or no-longer-passing policy is refused. Evidence it writes to `reports/evidence/` names the approval and is shown read-only in the dashboard. Verified end to end in the browser against the local API on September 19, 2026 (failing policy locked at 15/18; passing policy approved at 18/18). The dashboard never starts a paid run. |
| Sandbox integration | Access granted; not yet run | Official ConTree SDK installed and pinned; runner creates two branches, asks Nemotron for bounded actions, and measures pytest. On September 18 a read-only check returned `spawn=false`. On September 19, 2026 the same read-only `get_token_info()` check returned `spawn=true` and every reported permission true (`cancel`, `import`, `list`, `set_image_tag`, `spawn`, `spawn_disposable`). The SDK also warned "Token expires in 0 hours". No Sandbox has been run yet. |
| Public repository | Published and verified | [github.com/jessecalvin08/rulebranch](https://github.com/jessecalvin08/rulebranch) is public on `main`, with the README and MIT license visible. Private `.env` and local Devpost assets were excluded. |
| Public demo | Deployed and verified | [rulebranch.vercel.app](https://rulebranch.vercel.app/) serves the frontend as a safe static sample. It makes no Token Factory calls, exposes no credentials, and does not claim a real coding-agent or Sandbox run. |
| Demo video | Not recorded/uploaded | Outline prepared in release plan; recording must wait for a truthful working run |
| Devpost submission | Draft only | Complete near deadline after code, demo, video, and repository are ready |

## Next action for Jesse

Do not create or share another API key. Sandbox access is now granted (`spawn=true` on September 19, 2026), but the SDK warned the token expires within the hour, so confirm the credential is valid before a paid run. Then approve a policy in the local dashboard and run the command it gives you; the measured result appears in the dashboard's Sandbox evidence section. The current generated draft passed **18/18** local synthetic checks; that is not a coding-agent result.

Read [the debugging record](docs/07-compilation-debugging.md) for the confirmed causes, verification, limitations, and next steps. The local simulation does not need a Nebius API key.

## Next implementation milestones

1. Done: Sandbox permission confirmed (`spawn=true`, September 19, 2026). Check the credential's expiry before a paid run.
2. In the local dashboard, run the 18 checks on the sample or a generated draft, approve it, and run the `--approval` command it shows.
3. Run and debug the two real Nebius Sandbox branches, then verify the recorded agent actions and actual pytest outcomes.
4. Done: dashboard review/approval and read-only evidence display. Remaining: decide how judges see measured evidence on the public static site without a backend.
5. Record/upload the short public video, then complete Devpost submission after the real Sandbox evidence exists.
6. Confirm the remaining promotional balance before larger live runs; it has not been measured here.

## Decision log

| Decision | Chosen approach | Reason |
| --- | --- | --- |
| Project name | RuleBranch | Clearer hackathon product story than IntentGraph; avoids a conflicting AI product name |
| Track | Coding and Agentic Engineering | The app tests coding agents that write and test code in isolated sandboxes |
| Primary scenario | Coding agent | Stronger track fit than appointments or media workflow automation |
| Interface | React + FastAPI | A polished web demonstration with Python for AI and policy logic |
| Enforcement | Deterministic rules | A model must not be the sole judge of whether its own actions are safe |
| Demo data | Synthetic sample repository | Safe, repeatable, public, and free of real credentials |
| Run trigger | Dashboard approves; only the CLI runs | No HTTP endpoint can spend credits. The approval binds to the policy's SHA-256, so the CLI runs exactly what a person read, and the dashboard only reads evidence back |

## Important handling rule

Never paste a Nebius API key in chat, screenshots, public documents, GitHub, or source code. The existing key stays in ignored `backend/.env`; only the backend loads it. Debugging did not print or alter it.
