"use client";

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CitatieChip } from "@/components/werkplek/CitatieChip";
import type { NodeDoel } from "@/lib/annotatieNode";
import { markeerCitaties } from "@/lib/citaties";
import { markeerPassages } from "@/lib/markering";
import type { Bron } from "@/lib/types";

/** Rendert een agent-antwoord als (GitHub-flavored) Markdown. Geen rauwe HTML (geen rehype-raw), dus
 *  veilig; links laten we alleen door voor http(s) en openen extern.
 *
 *  **Gememoïseerd op de tekst.** Tijdens het streamen wordt de hele thread bij elke token opnieuw
 *  gerenderd; zonder dit parseerde react-markdown élk afgerond antwoord in het gesprek dan opnieuw,
 *  en groeiden de kosten mee met de lengte van het gesprek. Het lópende antwoord verandert wél per
 *  token en wordt dus nog steeds opnieuw geparseerd – dat schaalt met de lengte van dat ene antwoord
 *  en is de prijs voor opmaak die meteen goed staat. */
const TEKST_CLASS =
  "break-words text-[0.9375rem] leading-relaxed text-ink [overflow-wrap:anywhere]";

/** Het antwoord zoals het binnenkomt: platte tekst, dezelfde typografie als de opgemaakte versie.
 *
 *  Tijdens het streamen zou markdown bij élke token de hele tot dan toe ontvangen tekst opnieuw
 *  parseren – kosten die kwadratisch groeien met de lengte van het antwoord. De prijs is dat de
 *  opmaak (lijstjes, vet) pas verschijnt als de beurt klaar is; door dezelfde klassen te gebruiken
 *  blijft dat bij lopende tekst onzichtbaar en verspringt alleen wat écht opmaak heeft. */
export function StreamendeTekst({ tekst }: { tekst: string }) {
  return <div className={`whitespace-pre-wrap ${TEKST_CLASS}`}>{tekst}</div>;
}

export const Markdown = memo(function Markdown({
  tekst,
  nietLetterlijk,
  bronnen,
  onOpenSamenhang,
}: {
  tekst: string;
  /** Passages die de brongetrouwheidscontrole afkeurde (`grounding.niet_letterlijk`). */
  nietLetterlijk?: readonly string[];
  /** De bronnen van de beurt: een vindplaats die er éénduidig bij hoort wordt een citatie-chip. */
  bronnen?: readonly Bron[];
  onOpenSamenhang?: (doel: NodeDoel) => void;
}) {
  const teMarkeren = nietLetterlijk?.length ? nietLetterlijk : null;
  const plugins = [...(teMarkeren ? [markeerPassages(teMarkeren)] : []), ...(bronnen?.length ? [markeerCitaties(bronnen)] : [])];
  return (
    <div className={`space-y-3 ${TEKST_CLASS}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={plugins}
        components={{
          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          a: ({ href, children }) => {
            const veilig = typeof href === "string" && /^https?:\/\//i.test(href);
            return veilig ? (
              <a href={href} target="_blank" rel="noopener noreferrer" className="text-lint underline underline-offset-2">
                {children}
              </a>
            ) : (
              <span>{children}</span>
            );
          },
          ul: ({ children }) => <ul className="ml-4 list-disc space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="ml-4 list-decimal space-y-0.5">{children}</ol>,
          h1: ({ children }) => <p className="text-sm font-semibold text-lint">{children}</p>,
          h2: ({ children }) => <p className="text-sm font-semibold text-lint">{children}</p>,
          h3: ({ children }) => <p className="font-semibold">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          // Alleen gezet door `markeerPassages`: een citaat dat de controle afkeurde. Geel is hier
          // de aandacht-tint uit de huisstijl – dezelfde betekenis als op een reviewkaart: kijk hier
          // even naar. De stippellijn draagt het signaal óók zonder kleur, en de sr-only tekst zegt
          // het voor wie het niet ziet; kleur alleen zou het voor een deel van de lezers wegvallen.
          mark: ({ children, title }) => (
            <mark
              title={typeof title === "string" ? title : undefined}
              className="rounded-sm bg-aandacht-geel-bg px-0.5 text-aandacht-geel-tekst underline decoration-aandacht-geel-rand decoration-dotted underline-offset-2"
            >
              {children}
              <span className="sr-only"> (staat niet letterlijk in de opgehaalde tekst)</span>
            </mark>
          ),
          // Alleen gezet door `markeerCitaties`: een vindplaats die bij een bron van de beurt hoort.
          cite: ({ children, ...props }) => {
            const index = Number((props as Record<string, unknown>)["data-bron"]);
            const bron = bronnen?.[index];
            return bron ? <CitatieChip bron={bron} onOpenSamenhang={onOpenSamenhang}>{children}</CitatieChip> : <>{children}</>;
          },
          code: ({ children }) => <code className="rounded bg-surface px-1 py-0.5 font-mono text-xs">{children}</code>,
          pre: ({ children }) => (
            <pre className="overflow-x-auto rounded border border-line bg-surface p-2 font-mono text-xs">{children}</pre>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="border border-line px-2 py-1 text-left font-semibold">{children}</th>,
          td: ({ children }) => <td className="border border-line px-2 py-1 align-top">{children}</td>,
        }}
      >
        {tekst}
      </ReactMarkdown>
    </div>
  );
});
