# Viewer design notes

On 2026-10-23, at Jesse's request ("I don't like this UI", with the `jesse-2-ui` skill), the viewer was
redesigned from scratch. It no longer uses the Refero "OpenAI Developers" style, shadcnui-blocks or stock
shadcn primitives from the 2026-10-11 template build; those files are deleted. This supersedes the
template-only rule for the frontend until Jesse says otherwise.

## Direction

"A lab ledger": warm paper, one ink, one accent that means *branching*. Left-aligned, hairline rules,
mono for IDs and numbers, no cards, no icon tiles. Tokens live in `src/styles.css` (roles: paper, panel,
ink, muted, rule, accent). Inter is the only family; mono is the system stack.

The memorable move is the hero matrix in `sections/Results.tsx`: every one of the 79 tasks is a column,
in the same place in the three rows (branching, matched attempts, one attempt), so the whole benchmark
reads in one glance. Cells link to the replay.

## Research trail (what was actually consulted)

Only the title/slug search of the indexable sources was run (`jesse-2-ui/scripts/search.py`, queries
"dashboard results comparison" and "timeline trace"); no source page was opened and no reference was read
in depth. The hits (21st.dev comparison and usage dashboards, shadcn trace, React Bits ThoughtLine and
BranchedMenu, Aceternity timeline) informed only the choice to show the branch tree as an indented trace
rather than a table. Neither Aura, Neuform, MotionSites, Dribbble nor Refero was consulted. The skill's
20-reference minimum was not met.

## Impeccable critique pass (2026-10-23)

`/impeccable critique` scored the first redesign 27/40 (snapshot in `.impeccable/critique/`). Fixed in response:
both p-values and the full matrix now fit the first 800px of the page; the matrix is one tab stop per task
with arrow keys, and a touch tap pins a column; the replay has a task filter, branching-wins-first order,
previous/next, `?task=` and `?mode=` in the URL, a tabpanel, and retry buttons; red means branching and
selection only (failures are an ink-outlined tag; matched is ink, one attempt is mid grey, "both" is hatched);
kickers and section numbers were removed along with all coloured side borders (craft-floor bans); the replay
is a dark band; a glossary and a "rebuild these numbers" block were added. The detector reports no findings.
The page was not re-scored after these changes.

## Open items

1. No light/dark switch: the page is light with one dark band.
2. Hero cells are narrower than 24px on phones; the task list in the replay is the equivalent control.
3. Unused dependencies remain in `package.json` (radix-ui packages, `motion`, `cva`, `cn`); not pruned.

## Plain-language pass (2026-10-23)

A judge-with-no-context review found the page unreadable. Rewrote it as a story: what it is, how it works in four everyday steps, one real bug walked through (`sections/Walkthrough.tsx`, numbers read from the saved run), the evidence, then the explorable replay. Bugs are labelled "astropy #12907" with the report title instead of raw ids; attempts are numbered; tools, stop reasons and test counts are in words; technical detail lives in collapsed boxes.
