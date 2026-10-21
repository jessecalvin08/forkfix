import { useEffect, useState } from "react";

import Footer from "@/components/footer";
import Navbar from "@/components/navbar";
import { getJSON, type RunIndex } from "@/data";
import { Method } from "@/sections/Method";
import { RealIssues } from "@/sections/RealIssues";
import { Replay } from "@/sections/Replay";
import { Results } from "@/sections/Results";

export default function App() {
  const [index, setIndex] = useState<RunIndex | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getJSON<RunIndex>("/runs/index.json")
      .then(setIndex)
      .catch(() => setFailed(true));
  }, []);

  return (
    <div id="top">
      <a
        href="#result"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to the result
      </a>
      <Navbar />
      <main>
        {failed ? (
          <p role="alert" className="py-24 text-muted-foreground">
            The run data did not load. Reload the page to try again.
          </p>
        ) : null}
        {!index && !failed ? (
          <p aria-busy="true" className="py-24 text-muted-foreground">
            Loading results…
          </p>
        ) : null}
        {index ? (
          <>
            <Results index={index} />
            <Method />
            <Replay index={index} />
            <RealIssues />
          </>
        ) : null}
      </main>
      <Footer />
    </div>
  );
}
