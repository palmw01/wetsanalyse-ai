// Het antwoord als sjabloon (ADR-008), de spiegel van `packages/bronmodel/bronmodel/antwoord.py`: de
// blokken zijn een gesloten lijst, en `antwoord.test.ts` leest die bron. Klopt één blok niet of kent de
// werkplek het niet, dan geen sjabloon: `tekst` op het bericht is altijd het hele antwoord.

export interface AntwoordVindplaats { iri: string; label: string; jci: string; regeling: string }

export type AntwoordBlok =
  | { soort: "definities"; door: "bron"; items: { term: string; tekst: string; vindplaats: AntwoordVindplaats; bereik: string }[] }
  | { soort: "begrippen"; door: "bron"; items: { id: string; naam: string; status: string; definitie: string; werkgebied: string; werkgebied_id: string; herbeoordelen: boolean }[] }
  | { soort: "wettekst"; door: "bron"; items: { tekst: string; vindplaats: AntwoordVindplaats; nog_niet_in_werking?: boolean }[] }
  | { soort: "citaten"; door: "bron"; items: { tekst: string; vindplaats: AntwoordVindplaats; waarom: string }[] }
  | { soort: "verwijzingen"; door: "bron"; items: AntwoordVindplaats[] }
  | { soort: "annotaties"; door: "bron"; items: { id: string; klasse: string; tekst: string; vindplaats: string; bron_iri?: string }[]; totaal: number; volledig: boolean }
  | { soort: "toelichting"; door: "lex"; kop: string; tekst: string }
  | { soort: "twijfel"; door: "lex"; punten: string[] }
  | { soort: "extern"; door: "bron"; brontype: string; id: string; label: string; link: string; kop: string;
      passages: { nr: number; tekst: string; kop: string }[];
      /** De versie die Lex las: de hash van het document en de stand bij de bron. Leeg bij een ouder bericht. */
      bron_hash?: string; gewijzigd?: string }
  | { soort: "leemte"; door: "bron"; tekst: string }

export type BlokSoort = AntwoordBlok["soort"];

export interface Antwoord { sjabloon: string; versie: number; blokken: AntwoordBlok[]; doelen: AntwoordVindplaats[] }

export const BLOK_SOORTEN: readonly BlokSoort[] = ["definities", "begrippen", "wettekst", "citaten", "verwijzingen", "annotaties", "toelichting", "twijfel", "extern", "leemte"];

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
    case "extern": return typeof b.id === "string" && typeof b.label === "string" && typeof b.kop === "string" &&
      Array.isArray(b.passages) && b.passages.every((p) => isObject(p) && typeof p.tekst === "string");
  }
}

/** Streng: een sjabloon met een gat zou zich als volledig voordoen. */
export function parseAntwoord(v: unknown): Antwoord | undefined {
  if (!isObject(v) || typeof v.sjabloon !== "string" || !Array.isArray(v.blokken) || !v.blokken.length || !v.blokken.every(isBlok)) return undefined;
  return { sjabloon: v.sjabloon, versie: typeof v.versie === "number" ? v.versie : 1, blokken: v.blokken,
           doelen: Array.isArray(v.doelen) ? v.doelen.filter(isVindplaats) : [] };
}

/** Wat de controle in graph-qa niet leest (`NIET_GETOETST` in `bronmodel/antwoord.py`): afgeleide duiding en tekst van de code.
 *  Bestaat een antwoord alleen hieruit, dan is "niets te controleren" geen melding waard: er staat niets van het model. */
export const NIET_GETOETST: readonly BlokSoort[] = ["annotaties", "begrippen", "leemte"];

export function alleenNietGetoetst(a: Antwoord | undefined): boolean {
  return !!a && a.blokken.every((b) => NIET_GETOETST.includes(b.soort));
}

/** De bepalingen die je vanuit het antwoord naast het gesprek opent (ADR-008, *Detail bij een antwoord*): de doelen, en bij
 *  het sjabloon `annotaties` de bronnodes van de markeringen (een annotatie is geen bron, dus die staan niet in `doelen`). */
export function bepalingenVan(a: Antwoord): AntwoordVindplaats[] {
  if (a.doelen.length) return a.doelen;
  const uit = new Map<string, AntwoordVindplaats>();
  for (const b of a.blokken) {
    if (b.soort !== "annotaties") continue;
    for (const m of b.items) {
      if (m.bron_iri && !uit.has(m.bron_iri)) uit.set(m.bron_iri, { iri: m.bron_iri, label: m.vindplaats.replace(/ \(verouderd\)$/, ""), jci: "", regeling: "" });
    }
  }
  return [...uit.values()];
}

const LID = /^(.*:artikel:[^:]+):lid:([^:]+)$/;

export interface WettekstGroep<T> {
  /** Het artikel boven opeenvolgende leden, of niets bij een losse bepaling. */
  artikel?: AntwoordVindplaats;
  items: { item: T; lid?: string }[];
}

/** Opeenvolgende leden van één artikel onder één kop, met "lid N" bij elke tekst: twaalf keer "Artikel 9, lid N,
 *  Invorderingswet 1990" was ruis (acceptatie 7 nov 2026). Een los lid of onderdeel houdt zijn eigen vindplaats. */
export function groepeerWettekst<T extends { vindplaats: AntwoordVindplaats }>(items: readonly T[]): WettekstGroep<T>[] {
  const groepen: WettekstGroep<T>[] = [];
  for (const item of items) {
    const m = LID.exec(item.vindplaats.iri);
    const vorige = groepen.at(-1);
    if (m && vorige?.artikel?.iri === m[1]) { vorige.items.push({ item, lid: m[2] }); continue; }
    if (m && vorige && !vorige.artikel && vorige.items.length === 1 && LID.exec(vorige.items[0].item.vindplaats.iri)?.[1] === m[1]) {
      const eerste = vorige.items[0].item;
      vorige.artikel = {
        iri: m[1], label: eerste.vindplaats.label.replace(/, lid [^,]+$/, ""), regeling: eerste.vindplaats.regeling,
        jci: eerste.vindplaats.jci.replace(/&lid=[^&]*/, ""),
      };
      vorige.items = [{ item: eerste, lid: LID.exec(eerste.vindplaats.iri)![2] }, { item, lid: m[2] }];
      continue;
    }
    groepen.push({ items: [{ item }] });
  }
  return groepen;
}
