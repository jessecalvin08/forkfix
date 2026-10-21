import type * as React from "react";

export type StatCell = { value: string; label: string };

function Stats({ title, subtitle, cells, level = 2 }: { title: React.ReactNode; subtitle: string; cells: StatCell[]; level?: 1 | 2 }) {
  const H = level === 1 ? "h1" : "h2";
  return (
    <div className="mx-auto max-w-5xl px-6 py-20">
      <H className="text-balance text-center font-medium text-3xl tracking-tight sm:text-4xl md:text-4xl">
        {title}
      </H>
      <p className="mt-3.5 text-center text-muted-foreground text-xl tracking-[-0.015em] sm:text-lg md:text-2xl">
        {subtitle}
      </p>

      <div className="mt-14 grid grid-cols-1 overflow-hidden rounded-2xl border sm:grid-cols-2 md:grid-cols-3">
        {cells.map((cell, i) => (
          <div
            className={`-m-px border-t border-l p-10${i === 2 ? " sm:col-span-2 md:col-span-1" : ""}`}
            key={cell.label}
          >
            <span className="font-medium text-5xl">{cell.value}</span>
            <p className="mt-4 text-foreground/80 text-xl">{cell.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Stats;
