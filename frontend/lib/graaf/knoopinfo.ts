/** Wat de kennisgraaf over één knoop weet (`GET /v1/annotatie/knoop`, api/app/knoopinfo.py): geldigheid,
 *  herkomst, grondslag, "genoemd in", begrippen, vindplaats, de verwijzingen van en naar de knoop, en
 *  alle triples ruw. Letterlijk uit de graaf; de werkplek formatteert alleen. */
import { nodeRequest } from "@/lib/annotatieNode";

export interface KnoopWaarde {
  tekst: string;
  /** Een knoop in de graaf (`urn:bwb:…`): kiesbaar als hij op de kaart staat. */
  iri?: string;
  /** Een webadres (wetten.overheid.nl); alleen via `bronHref` in een `href`. */
  link?: string;
}
export interface KnoopFeit { eigenschap: string; waarden: KnoopWaarde[] }
export interface KnoopGroep { naam: string; feiten: KnoopFeit[] }
export interface KnoopVerwijzing {
  richting: "uit" | "in";
  van: string; naar: string; anker: string;
  /** intref | extref | tekstueel */
  soort: string;
  doel_soort: string; doel_pad: string;
  /** "laag" bij een verwijzing die alleen uit de tekst herkend is; leeg anders. */
  betrouwbaarheid: string;
}
export interface KnoopInfo {
  schema_versie: 1;
  bron_iri: string;
  beschikbaar: boolean;
  groepen: KnoopGroep[];
  ruw: { predicaat: string; waarde: string; iri?: string }[];
  verwijzingen: KnoopVerwijzing[];
}

export function haalKnoopInfo(iri: string): Promise<KnoopInfo> {
  return nodeRequest(`knoop?${new URLSearchParams({ bron_iri: iri })}`);
}

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
const MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"];

/** "2026-07-01" → "1 juli 2026". "9999-12-31" is in de BWB "geen einddatum". Anders ongewijzigd. */
export function datumTekst(waarde: string): string {
  const m = ISO.exec(waarde.trim());
  if (!m) return waarde;
  if (waarde.startsWith("9999-")) return "geen einddatum";
  const maand = MAANDEN[Number(m[2]) - 1];
  return maand ? `${Number(m[3])} ${maand} ${m[1]}` : waarde;
}

const SOORT: Record<string, string> = { intref: "binnen deze regeling", extref: "naar een andere regeling", tekstueel: "uit de tekst herkend" };

/** Wat een verwijzing is, in gewone woorden: "uit de tekst herkend · artikel", met het pad erbij. */
export function verwijzingTekst(v: Pick<KnoopVerwijzing, "soort" | "doel_soort" | "doel_pad">): string {
  return [SOORT[v.soort] ?? v.soort, v.doel_soort, v.doel_pad].filter(Boolean).join(" · ");
}

/** De verwijzing bij een regel in de relatielijst: zelfde andere knoop en, als die er is, dezelfde
 *  ankertekst. Een lijn in de graaf draagt alleen de ankertekst; de rest staat op de verwijzing. */
export function verwijzingVoor(verwijzingen: readonly KnoopVerwijzing[], richting: "uit" | "in", ander: string, anker: string): KnoopVerwijzing | undefined {
  const kandidaten = verwijzingen.filter((v) => v.richting === richting && (richting === "uit" ? v.naar : v.van) === ander);
  return kandidaten.find((v) => v.anker === anker) ?? (kandidaten.length === 1 ? kandidaten[0] : undefined);
}
