# Forkfix

A coding agent that searches over **checkpointed sandbox states** instead of making one attempt.
Every agent action runs in a Nebius Sandbox snapshot, so a trajectory can be forked at any step for
free. When the agent is about to change code, Forkfix samples several alternative changes, runs each
in its own fork, prunes weak branches with a judge model, and submits the best patch. The question it
answers: *does branching over real environment states let a small open model (NVIDIA Nemotron 3 Nano)
fix more real bugs than a normal one-attempt agent at comparable cost?*

Built for the Nebius x NVIDIA Global AI Hackathon, Coding & Agentic Engineering track.

## Status

**Benchmark (September 25-27, 2026): all 79 harness-eligible held-out SWE-bench Lite tasks, all 79
valid.** The first 40 ran September 25; the remaining 39 (`backend/benchmark_tasks_ext.json`, every
harness-eligible task the first list didn't take) ran September 27. Pooled by
`python -m forkfix.report --tasks-file benchmark_tasks.json benchmark_tasks_ext.json --modes
linear,branching,matched` into [`results/benchmark_all.json`](results/benchmark_all.json); the two
cohorts are also reported individually in [`results/benchmark.json`](results/benchmark.json) and
[`results/benchmark_ext.json`](results/benchmark_ext.json). Per-task reports are in the git-ignored
`backend/reports/day2/`.

| Mode (all Nemotron 3 Nano) | Solved | Any candidate correct | Model tokens | Est. model cost |
| --- | --- | --- | --- | --- |
| One attempt | 4 / 79 (5%) | 4 | 24.0M | $2.49 |
| Independent attempts, matched to branching's tokens on each task | 8 / 79 (10%) | 15 | 80.4M | $8.52 |
| **Branching over Sandbox snapshots** | **15 / 79 (19%)** | 18 | 81.0M | $9.83 |

- Against one attempt, branching wins 12 tasks to 1 (exact McNemar p = 0.003):
  **statistically significant.** At equal compute, branching solved 10 tasks the matched attempts did
  not; matched attempts solved 3 that branching did not (p = 0.092) — stronger than the first 40
  tasks alone (p = 0.22), but still short of the conventional 0.05 threshold.
- Every branching win came from a forked branch, and matched attempts spent at least as many tokens
  as branching on every task.
- What the forks did across all 79 tasks (`python -m forkfix.forks --tasks-file
  benchmark_tasks.json benchmark_tasks_ext.json` → [`results/forks_all.json`](results/forks_all.json)):
  378 fork points in 70 tasks; at 218 the sibling branches ended differently, and at 58 one branch
  reached a passing patch while a sibling did not (at 27 of those the passing branch started from a
  sampled alternative, not the agent's own action). Following the agent's own action at every fork
  reached a passing patch in only 5 of the 15 tasks branching solved; that path matches the separate
  one-attempt run's outcome on 11 of the 15, so it is a fair stand-in for "no forking".
- Absolute solve rates are low: Nemotron 3 Nano (3B active parameters) fails most tasks in every mode.
  The claim is the relative gain at equal cost, not a leaderboard score.
- Selection is still a weakness: on 3 tasks branching and on 7 tasks matched attempts had a correct
  candidate but submitted a different one.
- Cost: 185M tokens across both runs and all three modes, about $20.84 before tax at Token Factory
  list prices; about $0.12 per task for branching, whose judge calls use the pricier Nemotron 3
  Super. These are estimates: reports keep input/output tokens per mode, not per model, so each model
  is assumed to have its mode's split. 11,551 Sandbox runs reported about $108 of Sandbox cost, none
  of which has been billed during the Sandboxes beta.
- Not covered: 25 of 104 held-out pytest-based tasks could not be graded by our harness (mostly
  astropy and requests) and were excluded before sampling; django and sympy are out of scope.

Development runs (September 25) on 5 tasks that are excluded from the benchmark: a first comparison
(branching 2/5, one attempt 0/5) exposed a miscalibrated judge, a too-strict edit tool, fragile
model-call retries and a missing equal-cost baseline; a re-check after those fixes gave branching
3/5 vs 1/5 for both one attempt and 4 independent attempts, and revealed that the existing-test
check mistook intended behaviour changes for breakage (fixed before the benchmark).

Benchmark set (September 25): all 104 pytest-based SWE-bench Lite tasks not used in development were
checked; 79 grade correctly in our harness (unfixed fails, reference fix passes), and 25 do not
(mostly astropy and requests, whose suites need extra setup or network). 40 were drawn from the 79
with a fixed seed, proportionally by repository: `backend/benchmark_tasks.json`. The remaining 39
(`python -m forkfix.benchmark --rest` → `backend/benchmark_tasks_ext.json`) ran September 27, so the
benchmark now covers every task that grades correctly in our harness.

Earlier infrastructure checks (September 24): 16 Sandbox forks run in parallel with isolation intact,
and each task's official SWE-bench image grades correctly (unfixed fails, reference fix passes).

## Run viewer

`frontend/` is a static page that replays every benchmark run: the results table, then each task's
tree in all three modes, with every branch's actions, judge score, existing-test check, patch and
hidden-test grade. Its data (`frontend/public/runs/`, tracked) is exported from the same reports as
`results/benchmark.json`:

```powershell
cd backend; .\.venv\Scripts\python.exe -m forkfix.report; .\.venv\Scripts\python.exe -m forkfix.viewer_data
cd ..\frontend; npm install; npm run dev    # http://localhost:5173
```

## How it works

| Piece | File | Role |
| --- | --- | --- |
| Workspace | `backend/forkfix/workspace.py` | One snapshot per state; commands return a new snapshot, reads start nothing |
| Agent | `backend/forkfix/agent.py` | One JSON action per call: `bash`, `view`, `edit`, `create`, `submit` |
| Edits | `backend/forkfix/edits.py` | Accepts an edit despite pasted line numbers or wrong indentation, only when unambiguous |
| Search | `backend/forkfix/search.py` | Linear, independent attempts (fixed N, or matched to branching's token spend), or branching |
| Verify | `backend/forkfix/verify.py` | Runs the repo's existing tests (chosen from changed file names); broken candidates rank last |
| Benchmark | `backend/forkfix/benchmark.py` | Picks the benchmark tasks from validation reports with a fixed seed |
| Judge | `backend/forkfix/judge.py` | Nemotron 3 Super scores diffs from what the agent could see; never the hidden tests |
| Tasks | `backend/forkfix/tasks.py` | SWE-bench Lite loading and hidden-test grading (pytest-based repositories) |
| Driver | `backend/forkfix/run_day2.py` | Runs both modes on the same tasks and grades every candidate |
| Results | `backend/forkfix/report.py`, `viewer_data.py` | Aggregate saved reports into `results/benchmark.json` and the viewer's data |

## Run it

From `backend/` (Windows PowerShell; put `NEBIUS_API_KEY` and `NEBIUS_PROJECT_ID` in `backend/.env`):

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q                                  # offline tests, no credits
.\.venv\Scripts\python.exe -m forkfix.run_day2                           # dry run: prints the plan
.\.venv\Scripts\python.exe -m forkfix.run_day2 --validate-gold --pool heldout --parallel --approve  # check grading
.\.venv\Scripts\python.exe -m forkfix.benchmark --size 40 --seed 0     # writes benchmark_tasks.json
.\.venv\Scripts\python.exe -m forkfix.run_day2 --ids-file benchmark_tasks.json --parallel --approve
```

Runs that spend credits require `--approve` and stop at `--max-tokens`. Evidence goes to the
git-ignored `backend/reports/`.


## Benchmark extension (prepared, not run)

`backend/benchmark_tasks_ext.json` contains exactly the other 39 of the 79 harness-eligible tasks,
with no overlap with the original 40. Run the one-attempt, branching, and matched modes on these tasks to extend the three-way comparison.
Saved 40-task reports project roughly 82M tokens, 5,200 sandbox runs, and $9.40 in model charges
for all three modes across 39 tasks; actual difficulty and cost may differ. More tasks may strengthen
or weaken the result; significance is not promised. Run only after confirming promotional credit
coverage and approving the paid run. The original 40-task result remains the published evidence until new runs finish.

Free reporting commands from `backend/`, after the extension completes:

```powershell
.\.venv\Scripts\python.exe -m forkfix.report --tasks-file benchmark_tasks_ext.json --modes linear,branching,matched --out ..\results\benchmark_ext.json
.\.venv\Scripts\python.exe -m forkfix.report --tasks-file benchmark_tasks.json benchmark_tasks_ext.json --modes linear,branching,matched --out ..\results\benchmark_all.json
```

The combined report requires both compared modes on every included task, lists missing/failed tasks,
rejects duplicate task lists, and keeps each cohort's report cutoff. It includes all three modes only when each task has a valid report for every required mode.

Before buying credits, check the [official hackathon resources](https://nebiusglobalaihackathon.devpost.com/resources):
they advertise $25 Token Factory credits with the hackathon activation code, plus another $25 through
the free [Nebius Builders Program](https://dev.nebius.com/builders) (checked September 27, 2026).
Redemption eligibility and whether either offer was already claimed must be checked in the account.
The saved-run viewer and offline development need no model credits.

## History

This repository previously held RuleBranch, a permission-policy checker for coding agents, and was
itself named `rulebranch` on GitHub until it was renamed to `forkfix` on September 28, 2026.
RuleBranch is preserved on the local `archive/rulebranch` branch and in the git history before the
switch to Forkfix.

## License

MIT
