/** Het palet van de graaf: één plek voor kleuren en maten. De bronkleuren volgen de lintblauw-reeks
 *  van de huisstijl (donker = hoger in de opbouw), de markeringen hun JAS-klasse (`lib/jas.ts`, exact
 *  uit wa-table.png). De tekenaar krijgt concrete kleuren, want WebGL kent geen CSS-variabelen. */
import { jasStyle } from "@/lib/jas";
import { DEKKINGSKLEUR } from "@/lib/dekking";
import type { KnoopData, KnoopSoort, RelatieData } from "./model";

export const BRONKLEUR: Record<Exclude<KnoopSoort, "markering" | "klasse" | "begrip" | "impliciet">, string> = {
  regeling: "#154273", deel: "#2b5f8f", artikel: "#007bc7", lid: "#398ab8", onderdeel: "#6aa6cf", extern: "#94a3b8",
};
/** Omtrek van een bepaling buiten wat geladen is; binnenin wit. */
export const RANDKLEUR = "#7f9bb5";
export const RAND_VULLING = "#ffffff";
export { DEKKINGSKLEUR };
/** Wat niet bij de selectie of de focus hoort: zichtbaar als kaart, maar op de achtergrond. Donker
 *  genoeg om op het canvas (`#f7f9fc`) te blijven staan – gedimd is niet weg. */
export const GEDIMD = "#c3cdd8";
export const GEDIMDE_LIJN = "#e2e8ef";
/** Labels op de kaart: de broodtekstkleur (`--ink`). */
export const LABELKLEUR = "#1a1a1a";
/** Het label van een gedimde knoop: leesbaar om je op de kaart te oriënteren, maar duidelijk op de
 *  achtergrond. Het krijgt alleen ruimte die de nadruk overlaat (`lib/graaf/labels.ts`). */
export const GEDIMD_LABEL = "#7d8b9b";
/** Een lijn van of naar de gekozen knoop. */
export const NADRUK_LIJN = "#154273";

/** Begrippen (fase F3) in het paars van de huisstijl, los van de wettekst en van de JAS-klassen: een
 *  geaccordeerd begrip vol, een concept lichter, een vervangen begrip bijna grijs. Een voorgestelde
 *  relatie is geel, zoals elk voorstel van Lex in de werkplek. */
export const BEGRIPKLEUR: Record<string, string> = { geaccordeerd: "#5b2c83", concept: "#a684c6", vervangen: "#c8c0d2" };
export const VOORSTELKLEUR = "#d9a400";
/** Een wettelijk begrip: wat de wet zelf definieert, in donkerrood en dus niet in het paars van de
 *  analyse-uitkomsten. De herkomst hangt zo niet alleen aan de tekst. */
export const WETBEGRIPKLEUR = "#a90061";

/** Een beoordeelde relatie tussen markeringen (ADR-011): neutraal donker, zodat de klassekleuren van de
 *  markeringen het diagram dragen en de lijn de richting. */
export const RELATIEKLEUR = "#3d4b5c";

export const LIJNKLEUR: Record<RelatieData["soort"], string> = {
  bevat: "#a9bccf", verwijst_naar: "#6f9fc8", markeert: "#c3ccd6", heeft_klasse: "#c3ccd6",
  duidt: "#cdbddd", begripsrelatie: "#5b2c83", begripsvoorstel: VOORSTELKLEUR, definieert: WETBEGRIPKLEUR, komt_voor_in: "#dcb3c9",
  jas_relatie: RELATIEKLEUR,
};
/** Lijndikte in schermpixels. */
export const LIJNDIKTE: Record<RelatieData["soort"], number> = {
  bevat: 1, verwijst_naar: 1, markeert: 0.8, heeft_klasse: 0.8, duidt: 0.8, begripsrelatie: 1.4, begripsvoorstel: 1.2, definieert: 1.2, komt_voor_in: 0.8,
  jas_relatie: 1.4,
};

/** De stijl van een relatie tussen markeringen, naar haar beoordeling. Een voorstel van Lex is geel, zoals elk
 *  voorstel in de werkplek (`begripsvoorstel`), en een veranderde relatie ook: die vraagt opnieuw een oordeel. Een
 *  beoordeelde relatie is neutraal. Een afgewezen of vervangen relatie staat niet in beeld (vervangen is niet actueel, ADR-011). Altijd gericht: de leesvorm loopt van
 *  bron naar doel ("is plichthebbende van"). */
export function relatieStijl(a: Pick<RelatieData, "lifecycle" | "veranderd">): { kleur: string; zichtbaar: boolean } {
  if (a.lifecycle === "rejected" || a.lifecycle === "vervangen") return { kleur: RELATIEKLEUR, zichtbaar: false };
  return { kleur: a.lifecycle === "voorgesteld" || a.veranderd ? VOORSTELKLEUR : RELATIEKLEUR, zichtbaar: true };
}

/** Grootte in schermpixels bij zoom 1: de opbouw draagt het beeld, de details zijn klein. */
export const GROOTTE: Record<KnoopSoort, number> = {
  regeling: 13, deel: 8, klasse: 9, artikel: 5, lid: 3.5, onderdeel: 2.6, extern: 2.6, markering: 2.6, begrip: 6, impliciet: 3.4,
};
export const GEKOZEN_FACTOR = 1.6;

/** De kleur van een JAS-klasse, uit dezelfde bron als de badges. */
export function klasseKleur(klasse: string): string {
  return jasStyle(klasse).match(/bg-\[(#[a-f0-9]+)\]/i)?.[1] ?? "#cbd5e1";
}

/** Een impliciete partij (ADR-011) staat niet in de tekst: een holle knoop, wit met een omtrek in de kleur van
 *  haar klasse. Een stippelrand kan de tekenaar niet (WebGL, één knoopvorm); de legenda toont dezelfde holle stip. */
export const IMPLICIET_VULLING = "#ffffff";

/** De eigen kleur van een knoop, los van nadruk: een annotatie in haar klasse, een randbepaling wit
 *  (met omtrek), de wettekst in de lintblauw-reeks. Ook de stip in inspector, zoeklijst en legenda; bij een
 *  impliciete partij de kleur van haar omtrek. */
export function eigenKleur(a: Pick<KnoopData, "soort" | "klasse" | "label" | "rand" | "status" | "begrip_bron">): string {
  if (a.soort === "markering" || a.soort === "klasse" || a.soort === "impliciet") return klasseKleur(a.klasse || a.label);
  if (a.soort === "begrip" && a.begrip_bron === "wet") return WETBEGRIPKLEUR;
  if (a.soort === "begrip") return BEGRIPKLEUR[a.status ?? ""] ?? BEGRIPKLEUR.concept;
  return a.rand ? RAND_VULLING : BRONKLEUR[a.soort];
}
