// Het antwoord als sjabloon (ADR-008), de spiegel van `packages/bronmodel/bronmodel/antwoord.py`: de
// blokken zijn een gesloten lijst, en `antwoord.test.ts` leest die bron. Klopt één blok niet of kent de
// werkplek het niet, dan geen sjabloon: `tekst` op het bericht is altijd het hele antwoord.

export interface AntwoordVindplaats { iri: string; label: string; jci: string; regeling: string }

export type AntwoordBlok =
  | { soort: "definities"; door: "bron"; items: { term: string; tekst: string; vindplaats: AntwoordVindplaats; bereik: string }[] }
  | { soort: "begrippen"; door: "bron"; items: { id: string; naam: string; status: string; definitie: string; werkgebied: string; werkgebied_id: string; herbeoordelen: boolean }[] }
  | { soort: "wettekst"; door: "bron"; items: { tekst: string; vindplaats: AntwoordVindplaats }[] }
  | { soort: "citaten"; door: "bron"; items: { tekst: string; vindplaats: AntwoordVindplaats; waarom: string }[] }
  | { soort: "verwijzingen"; door: "bron"; items: AntwoordVindplaats[] }
  | { soort: "annotaties"; door: "bron"; items: { id: string; klasse: string; tekst: string; vindplaats: string }[]; totaal: number; volledig: boolean }
  | { soort: "toelichting"; door: "lex"; kop: string; tekst: string }
  | { soort: "twijfel"; door: "lex"; punten: string[] }
  | { soort: "leemte"; door: "bron"; tekst: string }

export type BlokSoort = AntwoordBlok["soort"];

export interface Antwoord { sjabloon: string; versie: number; blokken: AntwoordBlok[]; doelen: AntwoordVindplaats[] }

export const BLOK_SOORTEN: readonly BlokSoort[] = ["definities", "begrippen", "wettekst", "citaten", "verwijzingen", "annotaties", "toelichting", "twijfel", "leemte"];

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

const isVindplaats = (v: unknown): v is AntwoordVindplaats =>
  isObject(v) && typeof v.iri === "string" && typeof v.label === "string";

const metVindplaats = (x: unknown) => isObject(x) && typeof x.tekst === "string" && isVindplaats(x.vindplaats);

function isBlok(b: unknown): b is AntwoordBlok {
  if (!isObject(b) || !BLOK_SOORTEN.includes(b.soort as BlokSoort)) return false;
  const lijst = (toets: (x: unknown) => boolean) => Array.isArray(b.items) && b.items.every(toets);
  switch (b.soort as BlokSoort) {
    case "definities": case "wettekst": case "citaten": return lijst(metVindplaats);
    case "begrippen": return lijst((x) => isObject(x) && typeof x.id === "string" && typeof x.naam === "string");
    case "verwijzingen": return lijst(isVindplaats);
    case "annotaties": return lijst((x) => isObject(x) && typeof x.klasse === "string" && typeof x.tekst === "string");
    case "toelichting": case "leemte": return typeof b.tekst === "string";
    case "twijfel": return Array.isArray(b.punten) && b.punten.every((p) => typeof p === "string");
  }
}

/** Streng: een sjabloon met een gat zou zich als volledig voordoen. */
export function parseAntwoord(v: unknown): Antwoord | undefined {
  if (!isObject(v) || typeof v.sjabloon !== "string" || !Array.isArray(v.blokken) || !v.blokken.length || !v.blokken.every(isBlok)) return undefined;
  return { sjabloon: v.sjabloon, versie: typeof v.versie === "number" ? v.versie : 1, blokken: v.blokken,
           doelen: Array.isArray(v.doelen) ? v.doelen.filter(isVindplaats) : [] };
}
