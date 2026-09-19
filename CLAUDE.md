# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

RuleBranch (Nebius x NVIDIA hackathon, Coding & Agentic Engineering track, solo) turns plain-language agent permissions into an editable typed policy, checks it with a deterministic evaluator, and compares "observe" vs "enforce" runs. Design principle: the model (Nemotron via Nebius Token Factory) drafts policies; deterministic Python decides enforcement. `STATUS.md` is the source of truth for what is actually verified; `docs/03-architecture.md` describes the target design (SQLite, `/api/runs`, etc. are planned, not built).

## Repo and hosting

- Public repo: [github.com/jessecalvin08/rulebranch](https://github.com/jessecalvin08/rulebranch), branch `main`.
- Live demo: [rulebranch.vercel.app](https://rulebranch.vercel.app/), the `frontend/` build deployed on Vercel as a static sample. It has no backend, makes no Token Factory calls, and must not claim a live Sandbox run. Vercel project `jesse-dc66/rulebranch` is Git-connected: every push to `main` redeploys production, so pushing frontend changes publishes them immediately. Keep them truthful.

## Commands (Windows/PowerShell; a `backend/.venv` already exists)

Backend, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q                                          # all tests (offline)
.\.venv\Scripts\python.exe -m pytest tests/test_policy_engine.py::test_name -q   # single test
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000          # API
.\.venv\Scripts\python.exe -m app.run_sandbox --approval <sha256> --approve   # opt-in, spends credits; ID comes from the dashboard
.\.venv\Scripts\python.exe -m app.run_sandbox --reviewed-policy fixtures/sample_policy.json --approve --output reports/sandbox-comparison.json
```

Frontend, from `frontend/`: `npm run dev` (Vite on :5173, proxies `/api` to 127.0.0.1:8000), `npm run build` (`tsc -b && vite build`), `npm run check` (typecheck only). There is no linter or frontend test runner.

## Architecture

- `backend/app/main.py` – FastAPI routes. `/api/demo/*` serve a scripted fixture (`demo_data.py`); `/api/nebius/status` only lists models; `/api/policies/compile` calls Nemotron (503 without key, provider errors mapped to sanitized 502s); `/api/policies/validate` runs the local matrix; `/api/policies/approve` records an approval; `/api/approvals` and `/api/evidence` are read-only listings.
- `nebius_client.py` – OpenAI-SDK client for Token Factory; loads `backend/.env`. Compiles policy text with a JSON schema, re-validates with strict Pydantic (`GeneratedPolicy`), and always appends `MANDATORY_GUARDRAILS` (deny secret reads, deny network, approval for delete). `run_tests` rules must be exactly `["pytest"]`.
- `policy_engine.py` – `evaluate()`: default deny; precedence deny > approval_required > allow; paths are normalized and fail closed on absolute, traversal, or URL-like values.
- `policy_validation.py` – fixed 23-case synthetic matrix (5 permitted, 18 prohibited) applied to a draft; executes nothing.
- `approvals.py` – the review gate. An approval is `reports/approvals/<sha256>.json`, keyed by the SHA-256 of the policy's canonical JSON and written only after the server re-runs the matrix. `load_approval` re-derives the hash and re-runs the matrix, so a tampered or no-longer-passing policy is refused. The dashboard approves but never runs; only the CLI spends credits. The CLI writes evidence to `reports/evidence/` with `approval_id` and `policy_sha256`.
- `sandbox_runner.py` / `run_sandbox.py` – opt-in Nebius Sandbox (`contree_sdk`) experiment on `fixtures/coding_agent_repo` with a fake `.env` canary; two branches (observe/enforce), bounded agent actions, network/delete never executed. `diagnose_nebius.py` is NOT a permission probe: it makes one real, paid Nemotron policy-compilation call. The read-only Sandbox permission check is `ContreeSync(...).get_token_info()`, the same call `run_sandbox_comparison` makes before spending.
- `frontend/src` – `api.ts` gates every call on `hasLiveApi` (localhost or `VITE_API_BASE_URL`); the hosted Vercel build is a static sample using `demo.ts` fallback data.

## Constraints to respect

- Never read, print, or commit `backend/.env`; it holds the API key. Only `.env.example` is tracked. Never upload it as a fixture.
- Be truthful in docs, UI, and copy: live Nemotron policy generation is verified; a complete Sandbox comparison is NOT. Access was granted on September 19 (`spawn=true`) and one real run exists, but it is partial: enforce repaired the code with tests passing, observe stopped at step 1, and its two refused calls were invalid folder reads, not boundary attempts. Never present it as an observe-versus-enforce result. The dashboard comparison is a scripted simulation, not measured agent behavior. Don't add measured claims without real evidence in ignored `reports/`.
- Error paths must not leak provider response bodies or keys.
- Changes to the policy engine or guardrails need matching updates in `backend/tests/` (offline, no network).
