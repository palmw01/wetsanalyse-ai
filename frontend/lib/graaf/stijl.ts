/** Het palet van de graaf: één plek voor kleuren en maten. De bronkleuren volgen de lintblauw-reeks
 *  van de huisstijl (donker = hoger in de opbouw), de markeringen hun JAS-klasse (`lib/jas.ts`, exact
 *  uit wa-table.png). De tekenaar krijgt concrete kleuren, want WebGL kent geen CSS-variabelen. */
import { jasStyle } from "@/lib/jas";
import { DEKKINGSKLEUR } from "@/lib/dekking";
import type { KnoopData, KnoopSoort, RelatieData } from "./model";

export const BRONKLEUR: Record<Exclude<KnoopSoort, "markering" | "klasse" | "begrip">, string> = {
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

export const LIJNKLEUR: Record<RelatieData["soort"], string> = {
  bevat: "#a9bccf", verwijst_naar: "#6f9fc8", markeert: "#c3ccd6", heeft_klasse: "#c3ccd6",
  duidt: "#cdbddd", begripsrelatie: "#5b2c83", begripsvoorstel: VOORSTELKLEUR,
};
/** Lijndikte in schermpixels. */
export const LIJNDIKTE: Record<RelatieData["soort"], number> = {
  bevat: 1, verwijst_naar: 1, markeert: 0.8, heeft_klasse: 0.8, duidt: 0.8, begripsrelatie: 1.4, begripsvoorstel: 1.2,
};

/** Grootte in schermpixels bij zoom 1: de opbouw draagt het beeld, de details zijn klein. */
export const GROOTTE: Record<KnoopSoort, number> = {
  regeling: 13, deel: 8, klasse: 9, artikel: 5, lid: 3.5, onderdeel: 2.6, extern: 2.6, markering: 2.6, begrip: 6,
};
export const GEKOZEN_FACTOR = 1.6;

/** De kleur van een JAS-klasse, uit dezelfde bron als de badges. */
export function klasseKleur(klasse: string): string {
  return jasStyle(klasse).match(/bg-\[(#[a-f0-9]+)\]/i)?.[1] ?? "#cbd5e1";
}

/** De eigen kleur van een knoop, los van nadruk: een annotatie in haar klasse, een randbepaling wit
 *  (met omtrek), de wettekst in de lintblauw-reeks. Ook de stip in inspector, zoeklijst en legenda. */
export function eigenKleur(a: Pick<KnoopData, "soort" | "klasse" | "label" | "rand" | "status">): string {
  if (a.soort === "markering" || a.soort === "klasse") return klasseKleur(a.klasse || a.label);
  if (a.soort === "begrip") return BEGRIPKLEUR[a.status ?? ""] ?? BEGRIPKLEUR.concept;
  return a.rand ? RAND_VULLING : BRONKLEUR[a.soort];
}
