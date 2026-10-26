"use client";

import { jasStyle } from "@/lib/jas";
import type { NodeElement, NodeSegment } from "@/lib/annotatieNode";
import { spansVan } from "@/lib/graaf/spans";

/** De wettekst van een bepaling in de inspector, met de markeringen erin in hun JAS-kleur. Een klik
 *  op een markering kiest haar in de graaf – je blijft in de graaf. Spans staan alleen op hun ankers
 *  (`lib/graaf/spans.ts`). */
export function KnoopTekst({ segmenten, elementen, gekozen, kiesbaar, onKies, groot = false }: {
  segmenten: readonly NodeSegment[];
  elementen: readonly NodeElement[];
  /** Het element dat gekozen is: extra nadruk, de rest van de bepaling eromheen. */
  gekozen?: string;
  /** Staat deze markering op de kaart? Anders is de span alleen kleur: kiezen kan dan niet. */
  kiesbaar: (elementId: string) => boolean;
  onKies: (elementId: string) => void;
  /** Op een eigen pagina leesbaar groot, in de smalle inspector klein. */
  groot?: boolean;
}) {
  const perId = new Map(elementen.map((e) => [e.id, e]));
  const metTekst = segmenten.filter((s) => s.tekst.trim());
  if (!metTekst.length) return null;
  return <div className={`space-y-1.5 border-l-2 border-lint/20 pl-3 ${groot ? "text-sm leading-7" : "text-xs leading-relaxed"} text-ink`} data-testid="graaf-knooptekst">
    {metTekst.map((s) => {
      const nummer = s.nummer?.trim();
      return <p key={s.bron_iri} className={s.type === "Onderdeel" ? "pl-3" : ""}>
        {nummer && <span className="mr-1 text-faint">{nummer.endsWith(".") ? nummer : `${nummer}.`}</span>}
        {spansVan(s, elementen).map((stuk, i) => {
          const el = stuk.element ? perId.get(stuk.element) : undefined;
          if (!el) return <span key={i}>{stuk.tekst}</span>;
          const kleur = `rounded-sm border-b-2 px-0.5 box-decoration-clone ${jasStyle(el.klasse)}`;
          if (!kiesbaar(el.id)) return <mark key={i} title={el.klasse} data-element={el.id} className={kleur}>{stuk.tekst}</mark>;
          const kies = () => onKies(el.id);
          return <mark key={i} role="button" tabIndex={0} title={el.klasse} data-element={el.id}
            onClick={kies} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); kies(); } }}
            className={`focus-ring cursor-pointer ${kleur} ${gekozen === el.id ? "ring-2 ring-lint ring-offset-1" : gekozen ? "opacity-60" : ""}`}>
            {stuk.tekst}</mark>;
        })}
      </p>;
    })}
  </div>;
}
