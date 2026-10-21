import type { ReactNode } from "react";

/* The centred heading and subtitle exactly as the Features block sets them (features-01),
   for sections whose published block has no heading slot of its own. */
export function SectionIntro({ id, title, subtitle }: { id: string; title: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="px-6">
      <h2 id={id} className="mx-auto max-w-3xl text-center text-4xl font-medium tracking-tighter">
        {title}
      </h2>
      {subtitle ? (
        <p className="mx-auto mt-3 max-w-3xl text-pretty text-center text-lg text-muted-foreground tracking-[-0.01em] sm:text-2xl">
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}
