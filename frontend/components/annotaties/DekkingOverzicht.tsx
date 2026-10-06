"use client";

import { ChevronOmlaag } from "@/components/ui/Icoon";
import type { NodeDekking } from "@/lib/annotatieNode";
import { dekkingPerBron, gevondenTekst } from "@/lib/dekking";

/** Wat de detectoren per bronnode bekeken: welke van de detectiedimensies volledig draaiden en
 *  hoeveel zinsdelen niets opleverden. Een meting, geen oordeel – vandaar de zin eronder en geen
 *  kleur op "12 van 12". */
export function DekkingOverzicht({ dekking, volgorde, labelVan }: {
  dekking: NodeDekking;
  /** Bron-IRI's in de volgorde van de tekst. */
  volgorde: string[];
  labelVan: (bronIri: string) => string;
}) {
  const regels = dekkingPerBron(dekking, volgorde);
  if (!regels.length) return null;
  const onvolledig = regels.some((r) => r.onvolledig.length > 0);
  return (
    <details className="group rounded-kaart border border-line bg-surface/60 px-3 py-2 text-sm" data-testid="dekking">
      <summary className="focus-ring flex cursor-pointer list-none items-center gap-1.5 rounded text-xs font-medium text-muted">
        <ChevronOmlaag className="-rotate-90 transition-transform group-open:rotate-0" />
        Dekking
        {onvolledig && <span className="font-normal text-faint">(niet alle dimensies volledig bekeken)</span>}
      </summary>
      <ul className="mt-2 space-y-1.5">
        {regels.map((r) => <li key={r.bron_iri} className="text-xs">
          {regels.length > 1 && <span className="font-semibold text-muted">{labelVan(r.bron_iri)}: </span>}
          <span className="text-ink">{r.bekeken} van {r.totaal} dimensies volledig bekeken</span>
          <span className="text-muted"> · {r.ongedekt} {r.ongedekt === 1 ? "zinsdeel" : "zinsdelen"} zonder treffer</span>
          {/* Een kandidaat over de hele zin telt als treffer, terwijl er binnen de zin niets gevonden is. */}
          {!!r.alleenGeheel && <span className="text-muted" data-testid="dekking-geheel"
            title="Deze zinsdelen zijn alleen als geheel geraakt (bijvoorbeeld de hele normzin); binnen de zin vonden de detectoren niets.">
            {" "}· {r.alleenGeheel} alleen als geheel geraakt</span>}
          {/* Gezocht is niet hetzelfde als gevonden: per dimensie wat er aangetroffen werd. */}
          {r.gevonden && <p className="mt-0.5 pl-3 text-muted" data-testid="dekking-gevonden">{gevondenTekst(r.gevonden)}</p>}
          {r.onvolledig.length > 0 && <p className="mt-0.5 pl-3 text-muted">
            {r.onvolledig.map((o) => `${o.dimensie} ${o.stand}`).join(", ")}
          </p>}
        </li>)}
      </ul>
      <p className="mt-2 text-[11px] text-faint">
        Dit zegt welke patronen de detectoren konden bekijken – niet of de annotatie juist of volledig is.
      </p>
    </details>
  );
}
