# Devpost submission copy

Updated September 19, 2026 (facts only; the pitch wording is unchanged). This is the proposed copy for the Devpost draft. It deliberately distinguishes verified Token Factory generation and the hosted sample from the Sandbox evidence, which so far is one partial run. Revisit this copy once a complete observe-and-enforce comparison exists.

## Project overview

- **Name:** RuleBranch
- **Elevator pitch:** RuleBranch uses NVIDIA Nemotron to turn plain-language permissions into testable policies, then checks proposed coding-agent actions against clear safety boundaries.

## About the project

## Why RuleBranch

Coding agents are increasingly trusted to repair code and run tests. But a useful task permission is not unlimited authority: an agent allowed to edit `src/` should not also be able to read `.env`, inspect Git metadata, delete files, or send repository data to an external service.

RuleBranch makes that boundary visible and testable. A developer describes the work an agent may do in plain language. RuleBranch turns that description into structured policy rules, evaluates proposed tool calls against those rules, and presents a baseline-versus-enforced comparison with the exact rule responsible for each decision.

## What it does today

The public workbench includes a deliberately safe README-injection scenario. Its scripted baseline records an attempted `.env` read and an external upload; its enforced comparison blocks both attempts while allowing the source edit shown in the fixture. The site calls this a **sample simulation** throughout: it does not claim that a real agent, source edit, upload, or test run happened.

Behind the public sample, the private local FastAPI backend has made a verified live structured-policy generation call to NVIDIA Nemotron through Nebius Token Factory. The generated policy is hardened with local reserved guards and checked against an 18-case deterministic matrix. The current generated draft passed all 18 synthetic checks.

## How we built it

- **React, TypeScript, and Vite** power the public safety workbench.
- **Python and FastAPI** provide the private orchestration API and deterministic policy evaluator.
- **Nebius Token Factory** provides the live model integration.
- **NVIDIA Nemotron 3 Nano 30B A3B** generates typed policy drafts from a developer's authority statement.
- A deterministic evaluator—not the model alone—decides whether an action is allowed, denied, or needs approval.
- A bounded Nebius Sandbox runner compares two synthetic coding-agent branches. Access was granted on September 19, 2026. It contains an explicit approval gate, an eight-action limit per branch, and does not upload private repository content.

## What we learned and what remains

The central lesson is that an LLM can help express a policy, but deterministic enforcement and evidence must decide whether a coding agent acted within it. We also learned to keep credentials server-side, label simulations honestly, and make unsafe actions impossible in the test harness itself.

Nebius Sandbox access was granted on September 19, 2026, and one real run has been recorded, but it is partial: under enforcement, the Nemotron agent read the injected README without acting on it, repaired the code, and its tests passed; the observe branch stopped at its first step, so no before-and-after comparison is claimed. We will publish only inspected, measured evidence from a complete run.

## Links

- **Public demo:** https://rulebranch.vercel.app/
- **Public code:** https://github.com/jessecalvin08/rulebranch

## Built with tags

`Python`, `FastAPI`, `React`, `TypeScript`, `Vite`, `Nebius Token Factory`, `NVIDIA Nemotron`, `AI Agents`, `Developer Tools`, `Application Security`

## Video field

Leave blank until the public YouTube video is recorded and uploaded. The final recording must be three minutes or shorter and must show only truthful, verified behavior.

