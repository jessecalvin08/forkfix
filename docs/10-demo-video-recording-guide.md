# RuleBranch demo video recording guide

Target length: 2 minutes 40 seconds. Upload as a public YouTube video only after checking that no API key, billing balance, or `.env` file is visible.

## Before recording

1. Open the public demo: `https://rulebranch.vercel.app/`.
2. Open the public repository: `https://github.com/jessecalvin08/rulebranch`.
3. Use a browser profile/window without Token Factory, GitHub settings, email, terminal, or private files visible.
4. Record at 1080p if possible with computer audio or a clear voice-over.
5. Do not promise a completed Sandbox comparison. The public page is a labeled scripted sample. Sandbox access is granted and one partial run exists (September 19, 2026), but record this video only after a complete observe-and-enforce run, and update the script below to match it.

## Narration and screen plan

### 0:00–0:20 — problem

Show the RuleBranch home screen.

Say: “Coding agents need permission to fix code, but that permission should not include access to secrets or the ability to send repository data outside the workspace. RuleBranch tests those boundaries before a branch reaches the repository.”

### 0:20–0:55 — policy

Scroll to **Policy under review** and show the plain-language boundary plus rule list.

Say: “A developer writes the authority in plain language: read the README, source, and tests; write only under source; never read `.env`, Git metadata, delete files, or make network requests. RuleBranch represents that authority as structured rules.”

### 0:55–1:35 — baseline

Keep **Baseline** selected. Point out the README scenario, `.env` read, external collector request, and the **Unsafe** verdict.

Say: “The baseline is a transparent scripted fixture—not a claimed live run. It demonstrates the risk: untrusted README content leads an unprotected agent to attempt a secret read and an external upload.”

### 1:35–2:05 — enforcement

Select **Repair**. Point out both denied actions and the allowed source edit.

Say: “Under the reviewed policy, RuleBranch blocks the secret read and external request by rule ID, but still allows the legitimate source edit. The point is not to stop useful work; it is to stop actions outside the developer’s authority.”

### 2:05–2:30 — Nebius and NVIDIA

Return to top of page and open the GitHub README in a second tab if desired.

Say: “The private local backend uses Nebius Token Factory and NVIDIA Nemotron 3 Nano to compile a plain-language boundary into a typed policy draft. A deterministic evaluator then validates the result through an 18-case local matrix.”

### 2:30–2:40 — evidence and honesty

Show the **Next evidence** panel.

Say: “The Nebius Sandbox runner is implemented and has access. Our first real run is partial, so RuleBranch does not yet claim a before-and-after Sandbox result. The public demo and source code are linked below.” (Placeholder: rewrite once a complete run exists.)

## Upload checklist

- Title: `RuleBranch — bounded safety testing for coding agents`
- Visibility: **Public**
- Description links:
  - `https://rulebranch.vercel.app/`
  - `https://github.com/jessecalvin08/rulebranch`
- Verify duration is at most 3 minutes.
- Paste the final YouTube URL into Devpost only after the public page and playback both work.
