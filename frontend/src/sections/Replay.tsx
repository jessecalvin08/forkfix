import { useEffect, useMemo, useState } from "react";

import EventsTimeline, { type TimelineEvent } from "@/components/events-timeline";
import { SectionIntro } from "@/components/section-intro";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  MODES,
  MODE_LABEL,
  STOP_LABEL,
  eventFailed,
  fmtTokens,
  getJSON,
  patchFiles,
  type ModeName,
  type RunIndex,
  type RunNode,
  type TaskRun,
} from "@/data";

const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

/** The branching-only win with the widest tree: the clearest first run to open. */
function defaultTask(index: RunIndex): string {
  const wins = index.rows.filter((r) => r.modes.branching.solved && !r.modes.matched.solved && !r.modes.linear.solved);
  wins.sort((a, b) => b.modes.branching.branches - a.modes.branching.branches);
  return (wins[0] ?? index.rows[0]).task;
}

const tick = (b: boolean) => (b ? "Solved" : "–");

export function Replay({ index }: { index: RunIndex }) {
  const [task, setTask] = useState(() => defaultTask(index));
  const [mode, setMode] = useState<ModeName>("branching");
  const [node, setNode] = useState<string | null>(null);
  const [run, setRun] = useState<TaskRun | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setRun(null);
    setFailed(false);
    getJSON<TaskRun>(`/runs/${task}.json`)
      .then((r) => live && setRun(r))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [task]);

  const m = run?.modes[mode];
  const active: RunNode | undefined = useMemo(
    () => (m ? (m.nodes.find((n) => n.id === node) ?? m.nodes.find((n) => n.id === m.selected) ?? m.nodes[m.nodes.length - 1]) : undefined),
    [m, node],
  );
  const cand = active && m ? m.candidates[active.id] : undefined;
  const changed = cand ? patchFiles(cand.patch) : [];

  const events: TimelineEvent[] = active
    ? active.events.map((e) => ({
        title: cut(e.summary, 160),
        company: e.tool,
        period: `Step ${e.step}`,
        description: cut(e.observation, 500),
        technologies: eventFailed(e) ? ["failed"] : [],
      }))
    : [];

  return (
    <section id="replay" aria-labelledby="replay-title" className="py-12">
      <SectionIntro
        id="replay-title"
        title="Open any task and walk the branches the agent grew"
        subtitle="Each step is the agent's real action and the sandbox's real reply. A branch that reached a patch carries its judge score and its hidden-test grade."
      />

      <div className="mx-auto mt-12 grid max-w-(--breakpoint-lg) grid-cols-[minmax(0,1fr)] gap-6 px-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Tasks</CardTitle>
            <CardDescription>{index.rows.length} held-out tasks. Select one to replay it.</CardDescription>
          </CardHeader>
          <CardContent className="max-h-[32rem] overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Task</TableHead>
                  <TableHead>One</TableHead>
                  <TableHead>Matched</TableHead>
                  <TableHead>Branching</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {index.rows.map((r) => (
                  <TableRow
                    key={r.task}
                    data-state={r.task === task ? "selected" : undefined}
                    className="cursor-pointer"
                    tabIndex={0}
                    aria-selected={r.task === task}
                    onClick={() => {
                      setTask(r.task);
                      setNode(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setTask(r.task);
                        setNode(null);
                      }
                    }}
                  >
                    <TableCell className="max-w-[12rem] truncate font-medium" title={r.task}>
                      {r.task.replace("__", "/")}
                    </TableCell>
                    <TableCell>{tick(r.modes.linear.solved)}</TableCell>
                    <TableCell>{tick(r.modes.matched.solved)}</TableCell>
                    <TableCell>{tick(r.modes.branching.solved)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <div className="min-w-0 space-y-6">
          {failed ? (
            <p role="alert" className="text-muted-foreground">
              This run did not load. Reload the page to try again.
            </p>
          ) : null}
          {!run && !failed ? (
            <p aria-busy="true" className="text-muted-foreground">
              Loading {task}…
            </p>
          ) : null}
          {run && m ? (
            <>
              <Card className="shadow-none">
                <CardHeader>
                  <CardDescription>{run.repo}</CardDescription>
                  <CardTitle>{run.task}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="whitespace-pre-line text-sm text-muted-foreground">{cut(run.problem, 600)}</p>
                  <Tabs
                    value={mode}
                    onValueChange={(v) => {
                      setMode(v as ModeName);
                      setNode(null);
                    }}
                  >
                    <TabsList>
                      {MODES.map((x) => (
                        <TabsTrigger key={x} value={x}>
                          {MODE_LABEL[x]}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                  </Tabs>
                  <p className="text-sm">
                    <Badge variant={m.solved ? "default" : "secondary"}>{m.solved ? "Solved" : "Not solved"}</Badge>{" "}
                    <span className="text-muted-foreground">
                      {fmtTokens(m.tokens)} tokens · {m.sandbox_runs} sandbox runs · {m.nodes.length}{" "}
                      {m.nodes.length === 1 ? "branch" : "branches"}
                    </span>
                  </p>
                </CardContent>
              </Card>

              <Card className="shadow-none">
                <CardHeader>
                  <CardTitle>Branches</CardTitle>
                  <CardDescription>Select a branch to read its steps.</CardDescription>
                </CardHeader>
                <CardContent className="max-h-[20rem] overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Branch</TableHead>
                        <TableHead>Ended</TableHead>
                        <TableHead>Judge</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {m.nodes.map((n) => (
                        <TableRow
                          key={n.id}
                          data-state={n.id === active?.id ? "selected" : undefined}
                          className="cursor-pointer"
                          tabIndex={0}
                          aria-selected={n.id === active?.id}
                          onClick={() => setNode(n.id)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setNode(n.id);
                            }
                          }}
                        >
                          <TableCell className="font-medium">
                            {n.id}
                            {n.id === m.selected ? " · selected" : ""}
                          </TableCell>
                          <TableCell>{STOP_LABEL[n.stop] ?? n.stop}</TableCell>
                          <TableCell>{n.score == null ? "–" : n.score}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {active ? (
                <Card className="shadow-none">
                  <CardHeader>
                    <CardTitle>Branch {active.id}</CardTitle>
                    <CardDescription>
                      Steps {active.born + 1} to {active.end}, ended {STOP_LABEL[active.stop] ?? active.stop}.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {cand ? (
                      <div className="mb-4 space-y-1 text-sm">
                        <p>
                          <span className="font-medium">Hidden tests:</span> target {cand.fail_to_pass[0] ?? "?"} of{" "}
                          {cand.fail_to_pass[1] ?? "?"}, previously passing {cand.pass_to_pass[0] ?? "?"} of{" "}
                          {cand.pass_to_pass[1] ?? "?"}. <span className="font-medium">Judge:</span>{" "}
                          {cand.judge == null ? "n/a" : `${cand.judge} / 10`}.
                        </p>
                        {cand.existing_tests ? <p className="text-muted-foreground">{cand.existing_tests}</p> : null}
                        {changed.length ? (
                          <p className="text-muted-foreground">
                            Changes {changed.map((f) => `${f.path} (${f.meta})`).join(", ")}.
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    <EventsTimeline experiences={events} />
                    {cand ? (
                      <pre className="mt-4 max-h-96 overflow-auto rounded-lg bg-muted p-4 text-xs">{cut(cand.patch, 6000)}</pre>
                    ) : null}
                  </CardContent>
                </Card>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
