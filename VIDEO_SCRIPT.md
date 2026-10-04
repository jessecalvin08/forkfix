# Demo video script (target 2:45, hard limit 3:00)

Record the live viewer (rulebranch.vercel.app) in a clean browser. Every number below comes from
`results/benchmark_all.json`, `results/forks_all.json` or `frontend/public/fix/index.json`; recheck them against
those files before recording if anything has been re-run. At ~150 words per minute the voiceover is about 2:30.

| Time | On screen | Voiceover |
| --- | --- | --- |
| 0:00-0:20 | Top of the page: headline and nameplate | "Coding agents usually commit to one fix early. If that first edit is wrong, the rest of the run is wasted. Forkfix forks the sandbox before it changes code, tries several edits in parallel, and submits the strongest branch. It runs NVIDIA Nemotron 3 Nano on Nebius Sandboxes." |
| 0:20-1:15 | Open `astropy__astropy-12907`, branching mode, scrub the tree | "Here is a real SWE-bench task. At step nine the agent is about to edit. Forkfix snapshots the sandbox and tries three alternatives. One branch passes the hidden tests; the agent's own first choice does not. Each fork is a Nebius Sandbox snapshot, so the branches share nothing and a failed attempt costs almost nothing. This task was solved by branching and by neither the one-attempt run nor the matched attempts." |
| 1:15-2:05 | Results table and paired comparison | "We ran all 79 held-out, harness-validated pytest tasks in three modes. One attempt solved 4. Independent attempts with the same token budget solved 8. Branching solved 15. Against one attempt that is significant, p equals 0.003. Against matched attempts it is 10 tasks to 3, p equals 0.092: promising, not proven. Branching used about 81 million tokens, roughly ten dollars at list price." |
| 2:05-2:30 | "Real issues" section | "We also tried 13 real GitHub issues, where there are no hidden tests. The agent writes its own test, and we check every patch by hand. Three held up. Four passed the agent's own test and failed our review, one even with a perfect judge score. And those three came from issues we picked as clear bugs, so this is not a fix rate." |
| 2:30-2:45 | Method section, then repository link | "Nebius Sandboxes make the branching possible, Nemotron 3 Nano is the agent, Nemotron 3 Super is the judge. Everything you saw is replayable from saved runs. The code and viewer are public." |

## Checks before upload

- Length under 3:00 on the final export. Upload to YouTube as public or unlisted, whichever the rules allow.
- No credentials or `.env` contents on screen. Close other tabs.
- If you record anything live, label it "recording"; do not present a replay as a live run.
