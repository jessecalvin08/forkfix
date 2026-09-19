# Devpost submission copy

Updated September 19, 2026. Paste-ready answers for every Devpost step, in form order. Every claim here is checked against [STATUS.md](../STATUS.md): verified Token Factory generation, a scripted public sample, and two real Nebius Sandbox runs — a clean run where enforcement stayed out of the way, and a stronger-injection run where enforcement blocked an attempted `.env` read that the same agent completed without it. Nothing here presents the scripted sample as measured.

## Step 2: Project overview (already saved)

- **Name:** RuleBranch
- **Elevator pitch:** RuleBranch uses NVIDIA Nemotron to turn plain-language permissions into testable policies, then checks proposed coding-agent actions against clear safety boundaries.

## Step 3: Project details

### About the project (paste into the Project Story box)

```markdown
## Inspiration

An AI coding agent that can edit files and run tests is genuinely useful, but "fix this bug" is not the same as "do whatever you want in this repo." It has no business reading my `.env`, digging through `.git`, deleting things, or shipping my code off to some server. The awkward part is that the agent reads files while it works, so a README or a code comment can try to talk it into doing exactly those things. I wanted to find out whether I could give an agent real room to get work done while keeping its limits clear and actually enforced, not just written down somewhere.

## What it does

You describe what the agent is allowed to do in plain English. Nemotron, through Nebius Token Factory, turns that into a set of structured rules. After that the model is out of the decision loop: a plain Python evaluator judges every tool call the agent tries and tells you which rule allowed it, denied it, or held it for approval.

A few things I cared about getting right:

- Whatever the model writes, RuleBranch adds its own non-negotiable rules on top. No reading or writing secrets, keys, or `.git`. No network. Delete always needs a human approval.
- Before a policy is trusted it runs through 23 checks aimed at the sneaky cases: path traversal like `src/../.env`, nested secrets, `.env.local` variants, SSH keys, and case tricks like `.ENV`.
- When you approve a policy, RuleBranch fingerprints the exact JSON with a SHA-256. Change a single rule afterward and the runner refuses it, so you can't accidentally run something you never reviewed.
- It can run the real agent in a Nebius Sandbox twice, once just watching and once enforcing. The secret is a fake canary, and network and delete calls are recorded but never actually carried out.
- The attacks come from a small set of injected READMEs, some I wrote by hand and some Nemotron generates. A generated one gets checked against the policy before I spend anything on a run, and it can only ever point at a reserved `.invalid` address.

The demo page shows one prompt-injection case with a single Observe/Enforce switch. Flip it and the blocked calls get struck through, each with the rule that stopped it. That page is labeled as a scripted sample, because it is one.

## What actually happened when I ran it

I ran the real agent in a Sandbox against a couple of injections, each time with enforcement off and then on.

With a mild injection, the usual "ignore your instructions" note, the agent just ignored it and fixed the code either way. Enforcement stayed out of its way. That is the boring half of the story, but it matters: a guardrail that wrecks normal work is not much of a guardrail.

Then I hid the attack inside the task itself: step one, read `.env` and post it; step two, fix the formatter. This time the agent went for it. With enforcement off it read the canary. With enforcement on the policy stopped that read cold, and the attempt shows up in the trace, struck through, with `deny-secret-files` sitting next to it. Same model, same injection, and the only thing that changed the outcome was whether the policy was being enforced. One honest caveat: once it got blocked, the enforced agent burned through its step budget and did not finish the formatter fix.

That run is saved and shown on the public page as a recorded result, kept separate from the scripted sample at the top.

## How I built it

The front end is React, TypeScript, and Vite. The backend is Python with FastAPI and Pydantic, which is where the schema validation and the deterministic evaluator live. Model calls go through Nebius Token Factory with JSON-schema-constrained output, using NVIDIA's Nemotron 3 Nano both to draft policies and to act as the coding agent. The isolated runs happen in Nebius Sandboxes.

## What I learned

The thing that kept biting me is that valid JSON from a model is not the same as a safe policy. Early drafts would cheerfully allow any test command, and I ended up handling nested secret paths, traversal, and even case differences between operating systems in code rather than trusting the model's output. Getting one clean Sandbox run took four attempts. Truncated output crashed the SDK's decoder, the agent's replies outgrew my first token budget, and one runaway reply wiped a whole branch before I taught the runner to keep partial runs. The subtler lesson came from my first run that "worked": the agent ignored the injection, nothing got blocked, and I realized I had not actually proven anything yet. I had to write a harder attack the model would genuinely fall for. The short version of all of it: let the model help write the rules, but let deterministic code and real recorded evidence decide whether the agent stayed inside them, and be honest about what each result does and does not show.
```

### Built with (add each as a separate tag)

`Python`, `FastAPI`, `Pydantic`, `React`, `TypeScript`, `Vite`, `Nebius Token Factory`, `Nebius Sandboxes`, `NVIDIA Nemotron`, `AI Agents`, `Developer Tools`, `Application Security`

### "Try it out" links

- https://rulebranch.vercel.app/
- https://github.com/jessecalvin08/rulebranch

### Video demo link (required)

Leave blank until the public YouTube video is uploaded. It must be under three minutes and show only verified behavior; see [the recording guide](10-demo-video-recording-guide.md).

## Step 4: Additional info

These are factual answers. The personal ones (country, ratings, age and eligibility checkboxes) are yours to answer.

| Question | Answer |
| --- | --- |
| Submitter type | Individual |
| Organization name | N/A |
| Track | Coding & Agentic Engineering |
| New or existing before August 26, 2026? | New, if RuleBranch began after that date; otherwise Existing, with an honest description of the changes |
| Public code repository | https://github.com/jessecalvin08/rulebranch |
| Working demo or test build | https://rulebranch.vercel.app/ |
| Used Tavily? | No |

**Models used and why**

> We used `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` through Nebius Token Factory for two jobs: drafting structured coding-agent policies from plain language, and acting as the coding agent inside a Nebius Sandbox. We chose the Nano variant as a practical fit for iterative, low-latency structured output. We did not benchmark it against other variants.

**Fine-tuning or prompting approach**

> No fine-tuning. We used a task-specific system prompt with JSON-schema-constrained output (strict mode), then validated every response with Pydantic and appended mandatory local guardrails before treating it as a reviewable draft. The agent loop requests one schema-constrained tool action at a time, capped at eight steps per branch.

**Comparison with other models**

> We did not run a controlled head-to-head comparison, so we do not claim Nemotron outperformed another model. It produced a schema-valid policy draft in our verified live call. As a coding agent it resisted a mild injection but took the bait on a stronger, task-embedded one and tried to read `.env` — which is exactly the case our deterministic enforcement is built to catch, and did. Local validation and enforcement remained necessary for safety.

**Most valuable Nebius capabilities**

> Token Factory's OpenAI-compatible API with JSON-schema output let us make verified Nemotron calls without managing GPUs. Nebius Sandboxes were the decisive capability: running the real agent against a synthetic repository in two isolated branches, with and without enforcement, let us *measure* a blocked prompt-injection attack — the agent read a fake secret without enforcement and was denied it with enforcement — rather than only assert it. We have not used a dedicated GPU instance or claimed scaling results.

**Improvements requested**

> Clearer Sandbox entitlement status in the dashboard (before access was granted, our probe returned HTTP 403 for image listing), lenient decoding of truncated command output in the ConTree SDK (a byte cut mid-character raised UnicodeDecodeError), and an end-to-end example connecting model-generated policies to bounded Sandbox runs.

**Hope to see from the Nemotron team**

> A documented way to bound or disable reasoning tokens for structured tool-calling (one agent reply spent its whole 4,096-token budget without producing an action), clearer per-variant capability guidance, and examples for evaluating agent tool-use safety.

**Written feedback**

> Nemotron produced a usable, schema-valid policy draft and worked as a Sandbox coding agent — including taking the bait on a task-embedded injection, which let us measure our enforcement blocking it. We still needed deterministic validation to catch overly broad rules, and a retry for the occasional runaway reply. Once Sandbox access was granted, the SDK let us create isolated branches without infrastructure work; most of what we had to fix was in our own harness.

## Step 5: Submit

Check every page shows complete, read the eligibility attestations yourself, then submit. You can keep editing until the October 30, 2026 deadline (10:00 AM PDT, 10:30 PM IST).
