# UI template trail

The viewer was rebuilt on 2026-10-11 from published templates and components only, with none of the
earlier frontend reused. Each part below is used as published; only placeholder content, the
`next/link` dependency and token names were wired. Nothing here was designed from scratch.

## Direction and tokens

| Part | Source | URL | Licence |
| --- | --- | --- | --- |
| Visual system: "OpenAI Developers, stark white laboratory" (colour, type scale, 8px cards, pill controls, hairline surfaces) | Refero Styles | https://styles.refero.design/style/5c94c49f-0612-4261-842c-e1d501f3e13d | Reference style; typeface is Inter (the style's published substitute for proprietary OpenAI Sans) via `@fontsource-variable/inter` (SIL OFL) |

`src/styles.css` holds the style's published Tailwind v4 colour, type, radius and shadow tokens, its spacing
scale as plain variables (Tailwind v4 would read `--spacing-4: 4px` as the key `4` and shrink every spacing
utility), and the semantic names the components read pointed at those tokens. The style forbids a chromatic
accent, so chart state colours are neutrals; failed and waiting are also written as words. An earlier build
used the Refero "Vercel" style; it was replaced on 2026-10-11 at Jesse's request.

## Components

All from shadcnui-blocks (https://github.com/shadcnui-blocks, MIT, Copyright 2025 Shadcn UI Blocks), installed
as published. Their sample data became props; markup and classes are unchanged.

| Section | Block | URL | Slots filled |
| --- | --- | --- | --- |
| Nav | Navbar 02 | https://www.shadcnui-blocks.com/r/navbar-02.json | Logo, 4 links, 2 buttons; theme toggle removed; `aria-label` added to the icon-only menu button |
| Result | Stats 04 | https://www.shadcnui-blocks.com/r/stats-04.json | Heading, subtitle, three cells |
| What the numbers say | Features 01 | https://www.shadcnui-blocks.com/r/features-01.json | Heading, subtitle, three cards |
| Method | Timeline 05 | https://www.shadcnui-blocks.com/r/timeline-05.json | Four steps |
| Branch steps | Timeline 01 | https://www.shadcnui-blocks.com/r/timeline-01.json | Tool, summary, observation; icons swapped to Terminal and Hash |
| Task, branch and issue lists, tabs, cards | shadcn `table`, `tabs`, `card`, `badge` | https://ui.shadcn.com | Stock primitives (MIT) |
| Footer | Footer 01 | https://www.shadcnui-blocks.com/r/footer-01.json | Three link groups; `next/link` replaced by `a` |

## Considered and rejected

| Candidate | Why |
| --- | --- |
| ssych "Developer Tools Landing" (`simple-landing`) | Licence conflict: its README says "Bought once", the install page says landing pages are paid, the changelog says free |
| T3Code cinematic SaaS landing (21st) | Paid ($45); fake testimonials |
| ssych ui (all parts) | Dropped on 2026-10-11 at Jesse's request: it gave the page the same look as the first design |
| ssych Model Comparison | Needs latency, $/1M and context per model; Forkfix has none |
| ssych Tool Call Card | Requires a duration per call; events record none |
| ssych Stacked Bars | Time-series chart whose headline sums its rows; summing solved counts across modes is meaningless |
| ssych Trade Journal Table, Request Log, Release Feed | Trade, HTTP and release-note shaped data |
| hero-14 (21st, felipemenezes098) | AGPL-3.0; centred H1 over a photo with a logo strip |
| hero-06, hero-07 (shadcnui-blocks) | Centred, announcement badge, animated dot-grid wallpaper |
| hero-17, hero-with-mockup (21st) | Centred, gradient text and cursor glow |

## Open items

1. **Hero.** No published hero passed the slop checklist, so the page opens on Stats 04's centred heading.
2. **Branch tree and trace.** AI Conversation Tree (https://21st.dev/@elements-/components/conversation-tree, MIT)
   and Agent Trace (https://21st.dev/@n1m4mz/components/agent-trace, MIT) fit the data but their source needs a
   21st sign-in. Branches are a table until they are fetched.
3. **Type size.** The blocks set headings at 36px and stat numbers at 48px; the style caps type at 30px. Not
   restyled, per the template-only rule.
4. **Patch view.** The patch is a plain `<pre>`; a published code or diff block needs the 21st sign-in too.
