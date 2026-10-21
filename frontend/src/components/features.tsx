import type { LucideIcon } from "lucide-react";

export type Feature = { icon: LucideIcon; title: string; description: string };

const Features = ({ title, subtitle, features }: { title: string; subtitle: string; features: Feature[] }) => {
  return (
    <div className="px-6 py-20">
      <h2 className="mx-auto max-w-3xl text-center text-4xl font-medium tracking-tighter">
        {title}
      </h2>
      <p className="mt-3 text-pretty text-center text-lg text-muted-foreground tracking-[-0.01em] sm:text-2xl">
        {subtitle}
      </p>
      <div className="mx-auto mt-10 grid max-w-(--breakpoint-lg) gap-6 sm:mt-16 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((feature) => (
          <div
            className="flex flex-col rounded-xl border bg-card p-6"
            key={feature.title}
          >
            <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-full bg-muted">
              <feature.icon className="size-5" />
            </div>
            <span className="font-medium text-lg">{feature.title}</span>
            <p className="mt-1 text-[15px] text-foreground/80">
              {feature.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Features;
