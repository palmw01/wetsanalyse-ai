/** De wettekst van een bronknoop met de markeringen erin, voor de graafinspector: welke woorden van
 *  dit lid zijn gemarkeerd, en als wat.
 *
 *  Brongetrouw: een markering komt alleen in de tekst op haar **ankers** (offsets in codepoints binnen
 *  de bronnode, `bronmodel`), en alleen als de `bron_hash` van het anker die van het segment is. Geen
 *  tekstzoeken: een anker dat niet past, geeft geen span – de markering staat dan wel in de lijst
 *  eronder. Liever een span te weinig dan een op de verkeerde woorden. */
import type { NodeAnker, NodeSegment } from "@/lib/annotatieNode";
import { markeerbanen, type MarkeerSpan } from "@/lib/markeerbanen";

export interface TekstStuk {
  tekst: string;
  /** Het element met het vlak op dit stuk: een markering die geen andere omvat. */
  element?: string;
  /** De markeringen die andere omvatten en over dit stuk lopen, als baan eronder (0 = vlak onder de letters). */
  banen?: { element: string; baan: number }[];
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

/** Knipt de tekst van één segment in stukken met en zonder markering (optie B, `lib/markeerbanen.ts`): een markering
 *  die niets omvat is het `element` van een stuk (het vlak), een die andere omvat ligt als baan eronder. Zo valt geen
 *  markering weg in een langere. De stukken samen zijn exact de tekst van het segment; offsets in codepoints. */
export function spansVan(segment: Pick<NodeSegment, "bron_iri" | "tekst" | "bron_hash">, elementen: readonly SpanElement[]): TekstStuk[] {
  const tekens = Array.from(segment.tekst);
  if (!tekens.length) return [];
  const spans: MarkeerSpan[] = [];
  for (const el of elementen) {
    if (!isActueel(el)) continue;
    for (const a of el.ankers) {
      if (a.bron_iri !== segment.bron_iri || a.bron_hash !== segment.bron_hash) continue;
      spans.push({ sleutel: el.id, start: a.start, eind: a.eind });
    }
  }
  // De volgorde van de invoer beslist alleen bij gelijke lengte en plek; sorteer, zodat de volgorde van de elementen
  // niets uitmaakt.
  spans.sort((p, q) => p.start - q.start || p.eind - q.eind || (p.sleutel < q.sleutel ? -1 : p.sleutel > q.sleutel ? 1 : 0));
  const uit: TekstStuk[] = [];
  for (const stuk of markeerbanen(tekens.length, spans).stukken) {
    const t: TekstStuk = { tekst: tekens.slice(stuk.start, stuk.eind).join("") };
    if (stuk.vlak) t.element = stuk.vlak;
    if (stuk.banen.length) t.banen = stuk.banen.map((b) => ({ element: b.sleutel, baan: b.baan }));
    uit.push(t);
  }
  return uit;
}

/** Hoeveel banen een rij stukken nodig heeft: de regelhoogte van de alinea volgt het. */
export function aantalBanen(stukken: readonly { banen?: readonly { baan: number }[] }[]): number {
  return Math.max(0, ...stukken.flatMap((s) => (s.banen ?? []).map((b) => b.baan + 1)));
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
