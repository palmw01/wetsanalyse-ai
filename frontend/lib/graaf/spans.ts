/** De wettekst van een bronknoop met de markeringen erin, voor de graafinspector: welke woorden van
 *  dit lid zijn gemarkeerd, en als wat.
 *
 *  Brongetrouw: een markering komt alleen in de tekst op haar **ankers** (offsets in codepoints binnen
 *  de bronnode, `bronmodel`), en alleen als de `bron_hash` van het anker die van het segment is. Geen
 *  tekstzoeken: een anker dat niet past, geeft geen span – de markering staat dan wel in de lijst
 *  eronder. Liever een span te weinig dan een op de verkeerde woorden. */
import type { NodeAnker, NodeSegment } from "@/lib/annotatieNode";

export interface TekstStuk {
  tekst: string;
  /** Het element dat dit stuk markeert; bij overlap de kortste markering (die ligt erbovenop). */
  element?: string;
}

export interface SpanElement {
  id: string;
  ankers: readonly NodeAnker[];
  lifecycle?: string;
  verouderd?: boolean;
}

/** Een markering telt mee in de tekst als ze actueel is: niet verworpen en niet verouderd – dezelfde
 *  regel als de graaf (`api/app/samenhang.py:markeringen`). */
export const isActueel = (e: Pick<SpanElement, "lifecycle" | "verouderd">) => e.lifecycle !== "rejected" && !e.verouderd;

/** Knipt de tekst van één segment in stukken met en zonder markering. De stukken samen zijn exact de
 *  tekst van het segment. */
export function spansVan(segment: Pick<NodeSegment, "bron_iri" | "tekst" | "bron_hash">, elementen: readonly SpanElement[]): TekstStuk[] {
  const tekens = Array.from(segment.tekst);
  if (!tekens.length) return [];
  // Per codepoint het element met de kortste markering die hem raakt.
  const boven: (string | undefined)[] = new Array(tekens.length);
  const lengte: number[] = new Array(tekens.length).fill(Infinity);
  for (const el of elementen) {
    if (!isActueel(el)) continue;
    for (const a of el.ankers) {
      if (a.bron_iri !== segment.bron_iri || a.bron_hash !== segment.bron_hash) continue;
      const start = Math.max(0, a.start), eind = Math.min(tekens.length, a.eind);
      if (eind <= start) continue;
      const l = eind - start;
      for (let i = start; i < eind; i++) {
        if (l < lengte[i] || (l === lengte[i] && el.id < (boven[i] ?? ""))) { boven[i] = el.id; lengte[i] = l; }
      }
    }
  }
  const uit: TekstStuk[] = [];
  for (let i = 0; i < tekens.length; i++) {
    const vorig = uit.at(-1);
    if (vorig && vorig.element === boven[i]) vorig.tekst += tekens[i];
    else uit.push(boven[i] ? { tekst: tekens[i], element: boven[i] } : { tekst: tekens[i] });
  }
  return uit;
}

/** De segmenten van een weergave die bij een bronknoop horen: de knoop zelf en alles eronder, in
 *  tekstvolgorde. Leeg als de knoop niet in de weergave staat. */
export function segmentenVan(segmenten: readonly NodeSegment[], bron_iri: string): NodeSegment[] {
  const per = new Map(segmenten.map((s) => [s.bron_iri, s]));
  const hoortErbij = (s: NodeSegment) => {
    for (let x: NodeSegment | undefined = s, stap = 0; x && stap < 20; x = x.parent_iri ? per.get(x.parent_iri) : undefined, stap++) {
      if (x.bron_iri === bron_iri) return true;
    }
    // Een segment waarvan de ouder niet in de weergave staat (een lid zonder eigen tekst): op de IRI.
    return s.bron_iri.startsWith(`${bron_iri}:`);
  };
  return segmenten.filter(hoortErbij).sort((a, b) => a.volgorde - b.volgorde);
}
