import { Separator } from "@/components/ui/separator";

const footerSections = [
  {
    title: "On this page",
    links: [
      { title: "Result", href: "#result" },
      { title: "Method", href: "#method" },
      { title: "Replay", href: "#replay" },
      { title: "Real issues", href: "#real-issues" },
    ],
  },
  {
    title: "Source",
    links: [
      { title: "GitHub repository", href: "https://github.com/jessecalvin08/forkfix" },
      { title: "SWE-bench Lite", href: "https://www.swebench.com/" },
    ],
  },
  {
    title: "Built with",
    links: [
      { title: "Nebius Sandbox", href: "https://nebius.com/" },
      { title: "NVIDIA Nemotron", href: "https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/" },
    ],
  },
];

const Footer = () => {
  return (
    <footer className="border-t">
      <div className="mx-auto max-w-(--breakpoint-xl)">
        <div className="grid grid-cols-2 gap-x-8 gap-y-10 px-6 py-12 sm:grid-cols-3 xl:px-0">
          {footerSections.map(({ title, links }) => (
            <div key={title}>
              <h6 className="font-medium">{title}</h6>
              <ul className="mt-6 space-y-4">
                {links.map(({ title, href }) => (
                  <li key={title}>
                    <a className="text-muted-foreground hover:text-foreground" href={href}>
                      {title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <Separator />
        <div className="flex flex-col items-center justify-between gap-x-2 gap-y-4 px-6 py-8 sm:flex-row xl:px-0">
          <span className="font-medium">Forkfix</span>

          <span className="text-muted-foreground">
            A solo entry to the Nebius × NVIDIA Global AI Hackathon, Coding &amp; Agentic Engineering. Every number
            here is generated from saved run reports.
          </span>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
