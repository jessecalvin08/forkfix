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
reports record token splits by mode, not by model. The benchmark recorded 11,017 sandbox runs, which
were not billed during the Sandboxes beta at the time of the run.

## How it was built

Forkfix uses Nebius Token Factory for Nemotron model calls and Nebius Sandboxes for checkpointed workspaces. Reads use the saved image without starting an instance. Commands create new snapshots, so branches can work from the same state without sharing edits. The verifier selects existing tests using changed source filenames. The judge sees candidate patches and available checks, never the hidden grading tests. SWE-bench hidden tests grade the candidates after the agent has finished.

The benchmark includes a one-attempt baseline, a branching search, and independent attempts given the token budget used by branching on that task. Reports preserve the trees, actions, patches, checks, model-token counts, and grading results. A static viewer replays the saved runs; it does not run a live public agent.

## Real GitHub issues: not yet a result

We also pointed Forkfix at 13 open issues in 9 public repositories, where no hidden tests exist. The agent
writes a reproduction test first, and a branch counts as a fix only if that test fails on the unfixed repository
and passes on the branch, without breaking the project's existing tests. We reviewed every patch that passed by
hand, with a sandbox probe that runs inputs the agent's test never tried. Three held up (sqlparse, inflect and
humanize: each a one- or two-line change, checked against hundreds of other inputs and the project's own suite, at
a total of 2.7M model tokens, about $0.40 at list price). Four more passed the agent's own test and failed
review: one breaks a test the project already had, one fails on multi-line signatures and nested functions, one
rewrites strings such as 0123 to 123, and one (dateutil ISO week 53, 10/10 from the judge, all 255 existing tests
passing) rejects 49 valid ISO dates. So the proof check is necessary but not sufficient.

Please read this with its context. The first six issues, picked from bugs with no competing pull request, produced
no fix. The seven picked afterwards were clear bugs with exact examples, each already with someone else's open pull
request, so they are test cases and we have submitted nothing. Between the two rounds we also tightened the agent,
so we cannot say which change helped. Thirteen issues is not a benchmark, and we do not claim a fix rate on real
issues. The runs also exposed harness faults (an agent repeating a failing edit 34 times, an existing-test check
that ran no tests when pytest coloured its output), which we fixed.

## Feedback on the platforms (draft; all points are from our own logs and probes)

**Nebius Sandboxes (beta).** Checkpoint-and-branch is what made this project possible: 16 forks of one
snapshot ran in parallel in 7.8 s with isolation intact, and a fork costs nothing until it runs. Measured
limits that shaped the design: 50 concurrent instances, 3,600 s per instance, 8 concurrent image imports; a
SWE-bench image imported from Docker Hub in about 55 s. Requests: surface the per-instance limits and a
running cost in the API response (runs reported a `cost`, but no Sandbox charge appeared in billing during the
beta, so we could not tell what a branch would cost later); clearer errors when connections drop mid-run, since
transient transport failures were our biggest source of invalid runs and we had to add our own retry and
"infra stop" handling.

**Nebius Token Factory.** Strict `json_schema` output worked reliably for agent actions with Nemotron 3 Nano
and Super. Nemotron 3 Nano spends 3,000-4,000 tokens thinking before each action, so we needed a
`max_tokens` of 16,384 and a retry with thinking turned off (`enable_thinking: false`), which also worked.
Documenting that behaviour and the recommended setting for agent loops would have saved us a day.

**NVIDIA API catalog (probes on 2026-09-27; historical, not a current guarantee).** We tried to move the
benchmark to NVIDIA's hosted API to save credit. `nemotron-3-nano-30b-a3b` returned HTTP 410 (retired),
the listed `nemotron-nano-3-30b-a3b` returned 404, and the one working 30B-A3B model we found is a
different model whose free queue took 308 s for a single call. A model that is listed but returns 404, or
retired without redirecting, makes a fair comparison on a named model hard to reproduce.

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
- Working demo: the run viewer is live at https://forkfix.vercel.app (Vercel project renamed on
  October 7, 2026; the old `rulebranch.vercel.app` alias was removed).
- Demo video: add after recording the saved-run viewer.
