import { useEffect, useState } from "react";

import { SectionIntro } from "@/components/section-intro";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtTokens, getJSON, type RealIssue, type RealIssueIndex } from "@/data";

const verdict = (r: RealIssue) =>
  r.clean ? "Proven, no regressions" : r.proven ? "Proven" : r.candidates.length ? "No proof" : "No patch";

export function RealIssues() {
  const [data, setData] = useState<RealIssueIndex | null>(null);
  const [failed, setFailed] = useState(false);
  const [sel, setSel] = useState<string | null>(null);

  useEffect(() => {
    getJSON<RealIssueIndex>("/fix/index.json")
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  const issue = data?.rows.find((r) => r.issue === (sel ?? data.rows[0]?.issue));

  return (
    <section id="real-issues" aria-labelledby="real-issues-title" className="py-12">
      <SectionIntro
        id="real-issues-title"
        title="On real GitHub issues, the agent has to prove its own fix"
        subtitle={
          data
            ? `With no hidden tests, the agent writes a reproduction first. Of ${data.issues} issues, ${data.patched} produced a patch, ${data.proven} were proven, and ${data.clean} were proven without breaking an existing test.`
            : "With no hidden tests, the agent writes a reproduction first."
        }
      />

      {failed ? (
        <p role="alert" className="mx-auto mt-12 max-w-(--breakpoint-lg) px-6 text-muted-foreground">
          The real-issue results did not load. Reload the page to try again.
        </p>
      ) : null}

      {data && issue ? (
        <div className="mx-auto mt-12 grid max-w-(--breakpoint-lg) grid-cols-[minmax(0,1fr)] gap-6 px-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>Issues</CardTitle>
              <CardDescription>Select one to read its candidates.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Issue</TableHead>
                    <TableHead>Verdict</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.rows.map((r) => (
                    <TableRow
                      key={r.issue}
                      data-state={r.issue === issue.issue ? "selected" : undefined}
                      className="cursor-pointer"
                      tabIndex={0}
                      aria-selected={r.issue === issue.issue}
                      onClick={() => setSel(r.issue)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSel(r.issue);
                        }
                      }}
                    >
                      <TableCell className="font-medium">{r.issue}</TableCell>
                      <TableCell>{verdict(r)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card className="min-w-0 shadow-none">
            <CardHeader>
              <CardDescription>{issue.issue}</CardDescription>
              <CardTitle>{issue.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <p>
                <Badge variant={issue.proven ? "default" : "secondary"}>{verdict(issue)}</Badge>{" "}
                <span className="text-muted-foreground">
                  {fmtTokens(issue.tokens)} tokens · {issue.sandbox_runs} sandbox runs · commit{" "}
                  {issue.commit.slice(0, 7)} ·{" "}
                  <a className="underline underline-offset-4" href={issue.url}>
                    open on GitHub
                  </a>
                </span>
              </p>
              {issue.review ? (
                <p>
                  <span className="font-medium">Hand review: </span>
                  {issue.review}
                </p>
              ) : null}
              {issue.note ? <p className="text-muted-foreground">{issue.note}</p> : null}
              <ul className="divide-y border-y">
                {issue.candidates.map((c) => (
                  <li key={c.id} className="py-3 text-muted-foreground">
                    <span className="font-medium text-foreground">{c.id}</span> · {c.stop}, {c.steps} steps
                    {c.judge != null ? `, judge ${c.judge}` : ""}
                    {c.id === issue.selected ? " · selected" : ""} ·{" "}
                    {c.proven ? "reproduction test proves the fix" : "reproduction test does not prove it"}
                    {c.regressions ? ", breaks an existing test" : ""}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </section>
  );
}
