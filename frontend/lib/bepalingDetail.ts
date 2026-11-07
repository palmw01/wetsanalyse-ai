/** Wat de graaf over één bepaling weet, voor het paneel naast het gesprek (`GET /v1/annotatie/bepaling`,
 *  api/app/bepaling_detail.py; ADR-008 *Detail bij een antwoord*). De spiegel van
 *  `api/app/bepaling_graaf_contract.py`; `bepalingDetail.test.ts` leest die bron. Letterlijk uit de graaf, zonder model:
 *  de werkplek formatteert alleen. */
import type { AntwoordVindplaats } from "@/lib/antwoord";
import { nodeRequest } from "@/lib/annotatieNode";

export interface Structuurdeel { soort: string; nummer: string; titel: string; iri: string }
export interface Verwijzing { van: AntwoordVindplaats; naar: AntwoordVindplaats; anker: string; in_graaf: boolean; door: "bron" }
export interface Telling { aantal: number; items: AntwoordVindplaats[] }

export interface BepalingDetail {
  schema_versie: number;
  bron_iri: string;
  beschikbaar: boolean;
  vindplaats: AntwoordVindplaats;
  plaats: Structuurdeel[];
  status: string;
  inwerking: string | null;
  terugwerkend_tot: string | null;
  gewijzigd_bij: string;
  geldig_vanaf: string | null;
  geldig_tot: string | null;
  toestand_url: string;
  verwijst_naar: Verwijzing[];
  verwijst_naar_volledig: boolean;
  verwezen_door: Telling;
  grondslag_voor: Telling;
  bevoegdheid_voor: Telling;
  genoemd_in: Telling;
  definieert: string[];
}

/** De velden van `BepalingDetail`, in de volgorde van het contract: de drifttest vergelijkt ze met de Python-bron. */
export const BEPALING_DETAIL_VELDEN = [
  "schema_versie", "bron_iri", "beschikbaar", "vindplaats", "plaats", "status", "inwerking", "terugwerkend_tot", "gewijzigd_bij",
  "geldig_vanaf", "geldig_tot", "toestand_url", "verwijst_naar", "verwijst_naar_volledig", "verwezen_door", "grondslag_voor",
  "bevoegdheid_voor", "genoemd_in", "definieert",
] as const satisfies readonly (keyof BepalingDetail)[];

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isVindplaats = (v: unknown): v is AntwoordVindplaats => isObject(v) && typeof v.iri === "string" && typeof v.label === "string";
const isTelling = (v: unknown): v is Telling =>
  isObject(v) && typeof v.aantal === "number" && Array.isArray(v.items) && v.items.every(isVindplaats);

/** Streng: past het antwoord niet, dan geen detail (het paneel zegt dat), nooit een half detail. */
export function parseBepalingDetail(v: unknown): BepalingDetail | undefined {
  if (!isObject(v) || typeof v.bron_iri !== "string" || typeof v.beschikbaar !== "boolean" || !isVindplaats(v.vindplaats)) return undefined;
  if (!Array.isArray(v.plaats) || !v.plaats.every((p) => isObject(p) && typeof p.iri === "string" && typeof p.soort === "string")) return undefined;
  if (!Array.isArray(v.verwijst_naar) || !v.verwijst_naar.every((x) => isObject(x) && isVindplaats(x.van) && isVindplaats(x.naar))) return undefined;
  if (![v.verwezen_door, v.grondslag_voor, v.bevoegdheid_voor, v.genoemd_in].every(isTelling)) return undefined;
  if (!Array.isArray(v.definieert) || !v.definieert.every((d) => typeof d === "string")) return undefined;
  return v as unknown as BepalingDetail;
}

export async function haalBepalingDetail(iri: string): Promise<BepalingDetail | undefined> {
  return parseBepalingDetail(await nodeRequest(`bepaling?${new URLSearchParams({ bron_iri: iri })}`));
}

/** "Hoofdstuk VI – Aansprakelijkheid › Afdeling 1": de plek in gewone woorden, zonder het artikel zelf. */
export function plaatsZin(plaats: readonly Structuurdeel[]): string {
  const soortnaam = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  return plaats
    .filter((p) => p.soort !== "artikel" && p.soort !== "lid" && p.soort !== "onderdeel")
    .map((p) => [soortnaam(p.soort), p.nummer].filter(Boolean).join(" ") + (p.titel ? ` – ${p.titel}` : ""))
    .join(" › ");
}

/** De toestand die Lex las (`&g=` in de jci van de beurt), als de graaf nu een latere draagt; anders niets. Dan kan de tekst
 *  die het antwoord citeert intussen veranderd zijn, en het paneel zegt dat in plaats van het weg te poetsen. */
export function afwijkendeToestand(gelezenJci: string | undefined, geldigVanaf: string | null): string | undefined {
  const gelezen = /[&?]g=(\d{4}-\d{2}-\d{2})/.exec(gelezenJci ?? "")?.[1];
  return gelezen && geldigVanaf && geldigVanaf > gelezen ? gelezen : undefined;
}
