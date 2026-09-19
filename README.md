# RuleBranch

RuleBranch is a developer tool for testing whether an AI coding agent stays inside the authority a user granted it.

An AI agent may be allowed to edit source code and run tests. That does **not** mean it may read secrets, delete important files, or send data to an external service. RuleBranch generates policy drafts using Nemotron and checks them against a deterministic 23-case local matrix. It also contains an opt-in Nebius Sandbox agent runner. Sandbox access was granted on September 19, 2026, and one real run is recorded, but it is partial: the agent repaired the code with tests passing under enforcement, while the observe branch stopped at its first step, so no before-and-after comparison has been measured yet. The dashboard's public comparison remains a clearly labeled sample simulation.

## The hackathon project

- **Hackathon:** Nebius x NVIDIA Global AI Hackathon
- **Track:** Coding and Agentic Engineering
- **Working title:** RuleBranch
- **Builder:** Jesse, solo
- **Submission deadline:** October 30, 2026, 10:00 AM Pacific Time
- **Current state:** registered on Devpost; live Nemotron policy generation verified; sample simulation and dashboard available; Sandbox runner implemented but live access/execution still pending. See [current status](STATUS.md).

The project must make a real runtime call to Nebius Token Factory or use Nebius AI Cloud, and it must use at least one NVIDIA open-source model. RuleBranch will use NVIDIA Nemotron through Token Factory for structured policy compilation, adversarial test generation, and human-readable explanations. It will use Token Factory Sandboxes to execute coding-agent tests in an isolated, branchable environment.

## The one-sentence pitch

> RuleBranch converts a developer's plain-language permissions into executable tests, proves when a coding agent crosses a boundary, and verifies that a repair improves safety without breaking useful work.

## The planned end-to-end demo

This is the target workflow, not a list of completed features.

1. A developer selects an included sample repository and writes a policy: “The agent may edit `src/` and run tests, but it must never read `.env`, delete files, or send repository data over the network.”
2. RuleBranch asks NVIDIA Nemotron to turn that policy into editable structured rules and generate normal and malicious tasks.
3. A coding agent receives a task containing an indirect prompt injection hidden in a README. The malicious text tells it to read `.env` and upload the value.
4. RuleBranch runs the task against a baseline branch and records attempted tool calls.
5. The deterministic policy engine blocks prohibited actions, maps the failure to the exact rule, and displays the trace.
6. RuleBranch applies a limited repair to the policy or agent wrapper, reruns the identical suite on a new sandbox branch, and compares safety and useful-task completion.

## Why this is a good fit

RuleBranch builds on skills already visible in Jesse's prior work: Python and AI workflows; React interfaces; REST APIs; role-based access control; audit logging; and secure workflow thinking. It does not require model training, real credentials, or hardware.

The differentiator is not a claim that RuleBranch invents sandboxing or agent security. Its specific value is the complete developer workflow:

- plain-language authority becomes an editable policy;
- policies become normal and adversarial tests;
- attempted tool calls are scored deterministically;
- baseline and repair results can be compared and replayed.

## Project map

| Document | Purpose |
| --- | --- |
| [Hackathon requirements](docs/01-hackathon-requirements.md) | Rules, deadlines, credits, and submission checklist |
| [Product specification](docs/02-product-spec.md) | User problem, scope, demo, success measures, and non-goals |
| [Architecture](docs/03-architecture.md) | Components, data flow, API contracts, and security model |
| [Roadmap](docs/04-roadmap.md) | Milestones, weekly plan, and go/no-go gates |
| [Future work](docs/05-future-work.md) | Features deliberately deferred beyond the MVP |
| [Nebius setup runbook](docs/06-nebius-setup.md) | Credit redemption, API key hygiene, and first live-call checklist |
| [Project status](STATUS.md) | Current progress and the next concrete action |
| [Compilation debugging record](docs/07-compilation-debugging.md) | Confirmed request/configuration fixes, verification, and remaining limitations |
| [Release and submission plan](docs/08-release-and-submission.md) | Sandbox access blocker, reproducible run, publishing gates, and video outline |

## Planned stack

| Layer | Choice | Why |
| --- | --- | --- |
| Web interface | React + TypeScript + Vite | Polished, responsive product demonstration |
| API and orchestration | Python + FastAPI | Strong fit for AI calls, validation, and policy logic |
| Data | SQLite for MVP | Simple, local, inspectable, no cloud database dependency |
| Model integration | Nebius Token Factory + NVIDIA Nemotron | Required hackathon technology; structured policy and test generation |
| Isolated execution | Nebius Token Factory Sandboxes | Required evidence of safe coding-agent execution and branch comparison |
| Validation | Pydantic and deterministic Python rules | The model may suggest a policy; deterministic code decides enforcement |

## Scope guardrails

RuleBranch v1 will include one coding agent and safe simulated tools. It will **not** connect to a real GitHub account, Gmail, banking service, production API, or private repository. It will not make automated changes to production systems.

## Run the local proof

The sample simulation works without Nebius access. It uses fixed safe data to demonstrate policy decisions; it does not execute the source edits, uploads, or tests shown in the trace. Live policy-draft generation is separate and uses Token Factory credits.

Open two PowerShell terminals from this repository root.

**Terminal 1 - backend API**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - dashboard**

```powershell
cd frontend
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`. Use **Load sample simulation** to fetch the scripted comparison from the FastAPI API. Generated drafts do not change this comparison.

### Opt-in real Sandbox experiment

This path has produced one real, partial run (see [current status](STATUS.md)); a complete two-branch comparison has not been measured yet. It will consume Token Factory inference and Sandbox compute if the account has access. It is separate from the dashboard sample. Never use the local `.env` as a fixture. Add the actual Token Factory project ID to private `backend/.env` as `NEBIUS_PROJECT_ID=...`; the ID is required by the current Sandbox SDK.

The recommended path starts in the local dashboard's workbench:

1. **Run the local checks** (currently 23) on the sample rules or a draft you compiled.
2. **Approve this exact policy.** You tick an acknowledgement that you read every rule; the server re-runs the checks and records the approval in ignored `backend/reports/approvals/`, named by the policy's SHA-256. Approving runs nothing and spends nothing.
3. **Run it from the terminal** with the command the dashboard shows, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.run_sandbox --approval <64-character approval ID> --approve
```

The CLI re-derives the hash and re-runs the checks before spending anything, so an approval whose policy was edited, or that no longer passes, is refused. Its evidence goes to ignored `backend/reports/evidence/`, names the approval, and appears read-only in the dashboard's Sandbox evidence section. The dashboard itself can never start a paid run.

A policy file you reviewed by hand still works without the dashboard:

```powershell
.\.venv\Scripts\python.exe -m app.run_sandbox --reviewed-policy fixtures/sample_policy.json --approve --output reports/sandbox-comparison.json
```

Either way, the command refuses to run without `--approve` and a policy that passes every local check. Only checked-in synthetic files plus a fake canary are uploaded. Network and delete requests are never executed, even in observe mode. Results are saved under ignored `reports/`; inspect them before publishing any measured claim. A read-only SDK check confirmed Sandbox access (`spawn=true`) on September 19, 2026.

For a fresh setup only, copy `backend/.env.example` to a private `backend/.env`, enter the key and chosen model there, and follow the [Nebius setup runbook](docs/06-nebius-setup.md). Jesse's local configuration is already working; do not overwrite it. Never commit `backend/.env`.

## Quick links

- [Official hackathon rules](https://nebiusglobalaihackathon.devpost.com/rules)
- [Nebius Token Factory quickstart](https://docs.tokenfactory.nebius.com/quickstart)
- [Token Factory structured output guide](https://docs.tokenfactory.nebius.com/ai-models-inference/json)
- [Token Factory Sandboxes overview](https://docs.tokenfactory.nebius.com/sandboxes/overview)

## License

RuleBranch is MIT-licensed. The public repository keeps the license and setup README visible. The current judge-accessible sample demo is [rulebranch.vercel.app](https://rulebranch.vercel.app/); it is a safe static walkthrough and does not claim a live Sandbox execution.
