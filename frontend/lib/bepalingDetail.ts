/** Wat de graaf over één bepaling weet, voor het paneel naast het gesprek (`GET /v1/annotatie/bepaling`,
 *  api/app/bepaling_detail.py; ADR-008 *Detail bij een antwoord*). De spiegel van
 *  `api/app/bepaling_graaf_contract.py`; `bepalingDetail.test.ts` leest die bron. Letterlijk uit de graaf, zonder model:
 *  de werkplek formatteert alleen. */
import type { AntwoordVindplaats } from "@/lib/antwoord";
import { nodeRequest } from "@/lib/annotatieNode";

export interface Structuurdeel { soort: string; nummer: string; titel: string; iri: string }
export interface Verwijzing { van: AntwoordVindplaats; naar: AntwoordVindplaats; anker: string; in_graaf: boolean; door: "bron" }
/** `volledig: false` = het aantal kon niet geteld worden en is "minstens" (de rijen stonden op hun grens). */
export interface Telling { aantal: number; volledig: boolean; items: AntwoordVindplaats[] }

export interface BepalingDetail {
  schema_versie: number;
  bron_iri: string;
  beschikbaar: boolean;
  /** Met `jci` mét de toestand die de graaf draagt. */
  vindplaats: AntwoordVindplaats;
  bwb_id: string;
  /** De bepaling op wetten.overheid.nl. */
  url: string;
  plaats: Structuurdeel[];
  status: string;
  inwerking: string | null;
  terugwerkend_tot: string | null;
  gewijzigd_bij: string;
  geldig_vanaf: string | null;
  geldig_tot: string | null;
  toestand_url: string;
  verwijst_naar: Verwijzing[];
  verwijst_naar_aantal: number;
  verwijst_naar_volledig: boolean;
  verwezen_door: Telling;
  grondslag_voor: Telling;
  bevoegdheid_voor: Telling;
  genoemd_in: Telling;
  definieert: string[];
}

/** De velden van `BepalingDetail`, in de volgorde van het contract: de drifttest vergelijkt ze met de Python-bron. */
export const BEPALING_DETAIL_VELDEN = [
  "schema_versie", "bron_iri", "beschikbaar", "vindplaats", "bwb_id", "url", "plaats", "status", "inwerking", "terugwerkend_tot", "gewijzigd_bij",
  "geldig_vanaf", "geldig_tot", "toestand_url", "verwijst_naar", "verwijst_naar_aantal", "verwijst_naar_volledig", "verwezen_door", "grondslag_voor",
  "bevoegdheid_voor", "genoemd_in", "definieert",
] as const satisfies readonly (keyof BepalingDetail)[];

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isVindplaats = (v: unknown): v is AntwoordVindplaats => isObject(v) && typeof v.iri === "string" && typeof v.label === "string";
const isTelling = (v: unknown): v is Telling =>
  isObject(v) && typeof v.aantal === "number" && typeof v.volledig === "boolean" && Array.isArray(v.items) && v.items.every(isVindplaats);

/** Streng: past het antwoord niet, dan geen detail (het paneel zegt dat), nooit een half detail. */
export function parseBepalingDetail(v: unknown): BepalingDetail | undefined {
  if (!isObject(v) || typeof v.bron_iri !== "string" || typeof v.beschikbaar !== "boolean" || !isVindplaats(v.vindplaats)) return undefined;
  if (!Array.isArray(v.plaats) || !v.plaats.every((p) => isObject(p) && typeof p.iri === "string" && typeof p.soort === "string")) return undefined;
  if (!Array.isArray(v.verwijst_naar) || !v.verwijst_naar.every((x) => isObject(x) && isVindplaats(x.van) && isVindplaats(x.naar))) return undefined;
  if (![v.verwezen_door, v.grondslag_voor, v.bevoegdheid_voor, v.genoemd_in].every(isTelling)) return undefined;
  if (!Array.isArray(v.definieert) || !v.definieert.every((d) => typeof d === "string")) return undefined;
  return v as unknown as BepalingDetail;
}

/** Eén lezing per bepaling per sessie: de kop en het blok *Wat de graaf weet* vragen hetzelfde detail, en een tab die
 *  terugkomt laadt niet opnieuw. Een mislukte lezing gaat uit de cache, zodat opnieuw proberen echt opnieuw vraagt. */
const CACHE = new Map<string, Promise<BepalingDetail | undefined>>();
const MAX_CACHE = 64;

export function haalBepalingDetail(iri: string): Promise<BepalingDetail | undefined> {
  const bewaard = CACHE.get(iri);
  if (bewaard) return bewaard;
  const lezing = nodeRequest(`bepaling?${new URLSearchParams({ bron_iri: iri })}`).then(parseBepalingDetail);
  lezing.then((d) => { if (!d || !d.beschikbaar) CACHE.delete(iri); }, () => CACHE.delete(iri));
  if (CACHE.size >= MAX_CACHE) CACHE.delete(CACHE.keys().next().value as string);
  CACHE.set(iri, lezing);
  return lezing;
}

/** Een aantal zoals het paneel het noemt: exact als de api het telde, anders "minstens n". Een begrensde lijst rijen is
 *  nooit het totaal (de telquery kon falen; dan staat `volledig` op false en is het aantal een ondergrens). */
export function aantalTekst(aantal: number, volledig: boolean): string {
  return volledig ? String(aantal) : `minstens ${aantal}`;
}

/** Hoeveel er na de voorbeelden nog zijn, in dezelfde taal: "en 13 meer" of "en minstens 13 meer". */
export function meerTekst(t: Telling): string {
  const meer = t.aantal - t.items.length;
  return meer > 0 ? `en ${t.volledig ? "" : "minstens "}${meer} meer` : "";
}
