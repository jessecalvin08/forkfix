# Devpost draft: Forkfix

## Project name

Forkfix: Give Small Coding Agents More Than One Shot

## Tagline

A coding agent that forks real sandbox snapshots at code changes, tests alternatives, and submits the strongest patch.

## What it does

Coding agents often commit to one repair path early. Forkfix explores alternatives instead. It runs NVIDIA Nemotron 3 Nano inside Nebius Token Factory Sandboxes. When the agent is about to change code, Forkfix branches from the current sandbox snapshot, tries alternative edits in isolated trajectories, checks candidates with the repository's existing tests, and uses Nemotron 3 Super to help select a patch. SWE-bench's hidden tests are used only to grade completed candidates; the agent and judge never see them.

The project tests a focused question: can branching over real environment states help a small open model solve more software bugs than one attempt or independent attempts at comparable model-token cost?

## What we measured

We ran three modes on all 79 held-out, harness-validated pytest-based SWE-bench Lite tasks: 40 on
September 25, the remaining 39 on September 27. All 79 tasks produced valid runs.

| Mode | Selected patch solved | Model tokens | Estimated model cost |
| --- | ---: | ---: | ---: |
| One attempt | 4/79 (5%) | 24.0M | $2.49 |
| Independent attempts, matched to branching's per-task token spend | 8/79 (10%) | 80.4M | $8.52 |
| Branching over sandbox snapshots | 15/79 (19%) | 81.0M | $9.83 |

Against one attempt, branching wins 12 tasks to 1 (exact McNemar p = 0.003) — statistically
significant. At matched compute, branching solved 10 tasks that independent attempts did not;
independent attempts solved 3 that branching did not (p = 0.092), stronger than the first 40 tasks
alone (p = 0.22) but still short of the conventional 0.05 threshold. The absolute solve rates are low
for both baselines and for branching.

A saved-tree analysis found 378 fork points across 70 tasks. At 58 fork points, one sibling reached a
patch that passed the hidden tests while another did not; in 27 of those cases, the passing branch
began with a sampled alternative rather than the agent's own next action. Following the agent's own
action at every fork — an approximation of "no forking" — would still have solved only 5 of the 15
tasks branching won. Every selected branching win used a forked branch. The viewer lets reviewers
inspect every recorded run, branch decision, candidate patch, existing-test check, judge score, and
hidden-test grade.

The full run used about 185M model tokens across both cohorts and all three modes. Estimated total
model cost was about $20.84 before tax using Token Factory list prices; this is an estimate because
reports record token splits by mode, not by model. The benchmark recorded 11,551 sandbox runs, which
were not billed during the Sandboxes beta at the time of the run.

## How it was built

Forkfix uses Nebius Token Factory for Nemotron model calls and Nebius Sandboxes for checkpointed workspaces. Reads use the saved image without starting an instance. Commands create new snapshots, so branches can work from the same state without sharing edits. The verifier selects existing tests using changed source filenames. The judge sees candidate patches and available checks, never the hidden grading tests. SWE-bench hidden tests grade the candidates after the agent has finished.

The benchmark includes a one-attempt baseline, a branching search, and independent attempts given the token budget used by branching on that task. Reports preserve the trees, actions, patches, checks, model-token counts, and grading results. A static viewer replays the saved runs; it does not run a live public agent.

## Real GitHub issues: not yet a result

We also pointed Forkfix at 6 open issues in public repositories, where no hidden tests exist. The agent
writes a reproduction test first, and a branch counts as a fix only if that test fails on the unfixed
repository and passes on the branch. On this first live run, 4 of 6 runs produced a patch and none passed
the proof check. The judge model scored some of those patches up to 10/10, so we do not treat its score as
evidence. We changed the agent afterwards, and those changes have not been run live. We have not
submitted anything to any project, and we do not claim a fix rate on real issues.

## What we learned

The first five-task comparison exposed a miscalibrated judge, overly strict edit matching, fragile provider retries, and the need for an equal-compute baseline. We corrected those issues before the 40-task benchmark. We also found that a small number of existing tests can assert the old behavior even when an issue requests a deliberate behavior change, so those failures should inform the judge rather than automatically disqualify a patch.

Forking only helps if the search can produce meaningfully different candidates and the selection process can recognize the right one. On some tasks, a candidate passed hidden tests but the system selected another patch. Candidate selection remains a limitation.

## Limitations and next step

The benchmark now covers all 79 of 104 held-out pytest-based tasks whose grading harnesses were
validated; the other 25 (mostly astropy and requests) could not be graded reliably by our harness,
and Django and SymPy are outside its scope (different test runners). Branching's advantage over one
attempt is now statistically significant; its advantage over equal-compute independent attempts is
directionally consistent but not yet significant at conventional thresholds. Candidate selection is
also a real limitation: on several tasks a correct candidate existed but was not the one submitted.

## Demo video outline (under three minutes)

- 0:00–0:20 — Show why one repair attempt can get stuck.
- 0:20–1:30 — Replay a recorded run in the branch viewer; trace a branch from snapshot to patch and hidden-test grade.
- 1:30–2:20 — Show the three-mode results across all 79 tasks, model-token spend, estimated costs, and the p-values (significant vs. one attempt, not yet vs. matched attempts).
- 2:20–2:50 — Explain the roles of Nebius Sandboxes, Nemotron 3 Nano, and Nemotron 3 Super.
- 2:50–3:00 — Show repository and demo links.

## Links to fill before submission

- Public repository: https://github.com/jessecalvin08/forkfix (renamed from `rulebranch` on
  September 28, 2026; GitHub redirects the old URL).
- Working demo: the run viewer is now on `main`, so it will deploy to the existing Vercel site once
  Vercel rebuilds. The URL is still `rulebranch.vercel.app` unless the Vercel project itself is
  renamed (a separate step, not done here).
- Demo video: add after recording the saved-run viewer.
