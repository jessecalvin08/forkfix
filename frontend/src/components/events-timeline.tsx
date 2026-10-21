import { Hash, Terminal } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export type TimelineEvent = { title: string; company: string; period: string; description: string; technologies: string[] };

export default function EventsTimeline({ experiences }: { experiences: TimelineEvent[] }) {
  return (
    <div className="mx-auto max-w-(--breakpoint-sm) px-6 py-12 md:py-20">
      <div className="relative ml-3">
        {/* Timeline line */}
        <div className="absolute top-4 bottom-0 left-0 border-l-2" />

        {experiences.map(
          ({ company, description, period, technologies, title }, index) => (
            <div className="relative pb-12 pl-8 last:pb-0" key={index}>
              {/* Timeline dot */}
              <div className="absolute top-3 left-px h-3 w-3 -translate-x-1/2 rounded-full border-2 border-primary bg-background ring-8 ring-background" />

              {/* Content */}
              <div className="space-y-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent">
                    <Terminal className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <span className="font-medium text-base">{company}</span>
                </div>
                <div>
                  <h3 className="font-medium text-xl tracking-[-0.01em]">
                    {title}
                  </h3>
                  <div className="mt-2 flex items-center gap-2 text-sm">
                    <Hash className="h-4 w-4" />
                    <span>{period}</span>
                  </div>
                </div>
                <p className="text-pretty text-muted-foreground text-sm sm:text-base">
                  {description}
                </p>
                <div className="flex flex-wrap gap-2">
                  {technologies.map((tech) => (
                    <Badge
                      className="rounded-full"
                      key={tech}
                      variant="secondary"
                    >
                      {tech}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
