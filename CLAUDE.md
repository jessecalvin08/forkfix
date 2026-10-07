# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Forkfix (Nebius x NVIDIA hackathon, Coding & Agentic Engineering track, solo, deadline October 30,
2026 10:00 PDT) is a coding agent that forks Nebius Sandbox snapshots at code-changing steps, prunes
branches with a judge model, and submits the best patch. The claim to test: branching lets NVIDIA
Nemotron 3 Nano resolve more SWE-bench Lite tasks than a one-attempt agent at comparable cost.
`README.md`'s Status section is the source of truth for what is verified (the full 79-task benchmark,
September 25-27: branching beats one attempt significantly, p = 0.003; beats matched attempts
directionally, p = 0.092, short of the 0.05 threshold).

The repository was RuleBranch (a permission-policy checker for coding agents) until September 25,
2026, and was itself named `rulebranch` on GitHub until it was renamed to `forkfix` on September 28,
2026, when `main` was pushed with the Forkfix content, replacing RuleBranch on the public Vercel
site. RuleBranch is preserved on the local `archive/rulebranch` branch and in the git history before
the switch. The Vercel project was renamed to `forkfix` on October 7, 2026 and is live at
`forkfix.vercel.app`; the old `rulebranch.vercel.app` alias was removed.

## Commands (Windows; `backend/.venv` exists)

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q                                   # offline tests
.\.venv\Scripts\python.exe -m pytest tests/test_search.py::test_name -q   # single test
.\.venv\Scripts\python.exe -m forkfix.run_day2                            # dry run, spends nothing
.\.venv\Scripts\python.exe -m forkfix.run_day2 --validate-gold --approve  # paid: sandbox only
.\.venv\Scripts\python.exe -m forkfix.run_day2 --approve                  # paid: models + sandbox
.\.venv\Scripts\python.exe -m forkfix.run_day2 --ids-file benchmark_tasks.json --parallel --approve  # the benchmark
.\.venv\Scripts\python.exe -m forkfix.benchmark --size 40 --seed 0      # re-derive the benchmark list
.\.venv\Scripts\python.exe -m forkfix.fix <issue-url> --issue-file issue.json   # dry run on a real issue, spends nothing
.\.venv\Scripts\python.exe -m forkfix.fix <issue-url> --setup-only --approve   # paid: sandbox only, builds the repo env
.\.venv\Scripts\python.exe -m feasibility.check_access                    # free: token limits, models
.\.venv\Scripts\python.exe -m forkfix.report                             # free: results/benchmark.json
.\.venv\Scripts\python.exe -m forkfix.viewer_data                        # free: frontend/public/runs/
.\.venv\Scripts\python.exe -m forkfix.forks                              # free: results/forks.json
.\.venv\Scripts\python.exe -m forkfix.benchmark --rest                  # free: benchmark_tasks_ext.json (other 39)
.\.venv\Scripts\python.exe -m forkfix.run_day2 --ids-file benchmark_tasks_ext.json --modes linear,branching,matched --parallel --max-tokens 100000000 --max-spawns 7000 --approve  # paid: the extension
.\.venv\Scripts\python.exe -m forkfix.report --tasks-file benchmark_tasks_ext.json --modes linear,branching,matched --out ..\results\benchmark_ext.json
```

The previous session found no working direct NVIDIA endpoint for the benchmark's agent model
(2026-09-27): build.nvidia.com retired
`nemotron-3-nano-30b-a3b` (HTTP 410) and its listed `nemotron-nano-3-30b-a3b` returns 404; other
30B-A3B models there are different models, and its free queue took 308 s for one call. These are
historical probe results, not a current provider guarantee. OpenRouter still lists the original Nano
as free, with an unpaid account limited to 50 requests/day. Before buying credits, check the
hackathon resources and Nebius Builders Program for the separately advertised $25 grant. Never
assume it is unclaimed or launch paid runs without explicit approval.

From `frontend/`: `npm run dev` (viewer on :5173), `npm run build` (typecheck + build).

## Architecture

- `forkfix/workspace.py`: `SandboxWorkspace` wraps a ConTree image snapshot. `read` uses the image
  API (no instance); `run` spawns a non-disposable instance and returns a new workspace. `Meter`
  counts tokens, spawns and reported sandbox cost; child meters charge parents. Model calls check the
  token limit, sandbox runs check the spawn limit, and `enforce=False` meters are for finishing work
  (collecting patches, grading) that must not be lost at the limit.
- `forkfix/agent.py`: JSON-schema actions (strict mode needs every field present), tool execution,
  `Trajectory` (fork = copy messages/events, share the immutable workspace). File writes stage to
  `/tmp` then `cat >` to keep file modes. Paths outside `/testbed` are refused.
- `forkfix/search.py`: lockstep rounds over live trajectories; `roots` > 1 is the sampled baseline;
  branching only at `edit`/`create`; above `width`, rank by (no regressions in existing tests, judge
  score); final selection prefers non-regressing, then submitted, then judge score.
- `forkfix/verify.py`: picks existing test files from changed *source* file names (never from the
  hidden test patch), runs them on the base repo once (cached) and on each candidate. `broken` =
  errors/collection failure or >50% of previously passing tests fail; fewer failures are passed to
  the judge as a possibly intended behaviour change (pytest-5227 changes an asserted log format).
- Modes: `linear`, `branching`, `matched` (independent attempts given exactly branching's token spend
  on the same task; runs after branching), `sampled` (fixed N). Reports: `reports/day2/` for runs,
  `reports/validation/` for harness checks; `benchmark_tasks.json` (tracked) is the benchmark list.
- `forkfix/edits.py`: edit matching that tolerates pasted `view` line numbers and whitespace, with a
  uniform re-indent; ambiguous or missing matches are refused with line numbers / the closest text.
- Agent calls try thinking, then no-thinking, then no-thinking at temperature 0.7 (3 attempts).
- `forkfix/tasks.py`: SWE-bench Lite rows cached in ignored `reports/swe_bench_lite.json`; image name
  `swebench/sweb.eval.x86_64.<id lower, "__" -> "_1776_">:latest`; grading resets test files, applies
  the hidden test patch, runs `pytest -rA`, returns only summary lines. django/sympy are excluded
  (different test runners).
- `forkfix/repo.py` + `forkfix/fix.py` (real-issue mode, Oct 2026, not yet run live): `setup_script` clones a public repo
  into a `python:3.11` sandbox with a venv at `/opt/venv`; `real_task` has no hidden tests and `repro_first=True`, so the
  agent must write `/testbed/forkfix_repro_test.py` first. `Verifier.check_repro` runs it on the base repo (must exit 1)
  and on each branch (must exit 0); a proven fix outranks judge score in `Search._rank`. SWE-bench prompts are unchanged.
- `tests/fakes.py`: `FakeWorkspace`, `FakeAgent`, `FakeJudge` for fully offline tests.
- `forkfix/report.py` aggregates the newest report per benchmark task (written after
  `benchmark_tasks.json`) into tracked `results/benchmark.json`, with McNemar p-values and a list-price
  cost estimate; `forkfix/viewer_data.py` exports the same reports' trees for the viewer.
- `frontend/`: Vite + React static run viewer (results, then a per-task tree over agent steps with
  each branch's events, judge score, patch and hidden-test grade). Visual system carried over from
  RuleBranch: graphite on bone paper, and `--fix` green is the only colour, reserved for patches that
  passed the hidden tests and the route to them.

## Constraints to respect

- Never read, print, or commit `backend/.env`. Only `.env.example` is tracked.
- Jesse's standing rule (2026-09-30): do not spend Nebius Token Factory credit; find another way (fakes, saved-report replays,
  sandbox-only checks) and only surface a live model run as a last resort, for Jesse to decide.
- Paid runs (anything with `--approve`, any probe in `feasibility/` except `check_access`) need Jesse's
  explicit go-ahead. Credit is currently very low (trial only); see memory.
- Hidden tests must never reach the agent or the judge; they are used only to grade.
- Be truthful in docs and copy: report solve rates only from saved evidence in `reports/`, and report
  cost alongside every comparison.
- Error paths must not leak provider response bodies or keys (log exception type names only).
