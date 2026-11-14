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
      passages: { nr: number; tekst: string; kop: string; soort?: "alinea" | "voetnoot" | "tabel" | "tabelrij"; cellen?: string[] | null;
        verwijst_naar?: { id: string; label: string; link: string }[] | null; plek?: string }[];
      /** De versie die Lex las: de hash van het document en de stand bij de bron. Leeg bij een ouder bericht. */
      bron_hash?: string; gewijzigd?: string;
      /** Wat de bron tegenover de wet is, uit de code (`status_regel` van de connector); leeg bij een ouder bericht. */
      status_regel?: string;
      /** Uit de metadata van het gelezen stuk: de datum en het soort ("Motie"). Leeg bij een ouder bericht. */
      datum?: string; soort_stuk?: string } & TekstBij
  | { soort: "stukken"; door: "bron"; brontype: string; kop: string; items: StukRij[];
      /** Wat er gezocht is, in woorden van de code; en hoeveel stukken er bij de bron aan voldoen. */
      zoekvraag?: string; totaal?: number | null;
      /** Bij een telvraag: het aantal dat de bron zelf telt, met de verdeling die de bron geeft (`Telling` in bronmodel). */
      telling?: Telling | null }
  | { soort: "leemte"; door: "bron"; tekst: string }

/** Het antwoord op een telvraag, uit de bron: `dekking` "ten minste" bij een bron die een ondergrens geeft (LiDO). */
export interface Telling {
  aantal: number; dekking?: "precies" | "ten minste"; bron?: string; per_wat?: string;
  per?: { waarde: string; aantal: number }[]; zonder_verdeling?: string;
}

/** De vaste zin van een telling, zoals `telling_tekst` in `bronmodel/antwoord.py` (zonder de verdeling). */
export function tellingTekst(t: Telling): string {
  const n = `${t.dekking === "ten minste" ? "ten minste " : ""}${new Intl.NumberFormat("nl-NL").format(t.aantal)} ${t.aantal === 1 ? "stuk" : "stukken"}`;
  return `${t.bron ? `${t.bron} telt` : "De bron telt"} ${n} bij deze zoekvraag.`;
}

/** Bij welke tekst van de bepaling een stuk hoort (een uitspraak bij een eerdere versie van het artikel), uit de bron.
 *  `tekststand` staat tegenover de tekst in de graaf; `op_peildatum` alleen als Lex met een peildatum zocht. */
export interface TekstBij {
  tekst_vanaf?: string; tekst_tot?: string; tekststand?: "huidige tekst" | "eerdere tekst" | "onbekend" | string;
  op_peildatum?: boolean | null;
  /** De stand van het stuk bij de bron; bij een kennisgroepstandpunt geldend, ingetrokken of vervallen. */
  status?: string; vervangen_door?: string[];
}

/** Eén gevonden stuk in een lijst, met de metadata uit de zoektool (de sleutels van `METADATA_SLEUTELS`). */
export interface StukRij extends TekstBij {
  id: string; label: string; link?: string; soort?: string; titel?: string; datum?: string; gepubliceerd?: string;
  jaar?: string; orgaan?: string; indieners?: string[]; reeks?: string[]; gezamenlijk?: string[]; status?: string; versie?: string; leesbaar?: boolean;
  /** Waarom er geen tekst is (`leesbaar: false`), in de woorden van de connector: "onopgemaakt, alleen PDF", "geen tekst in de open data". */
  zonder_tekst?: string;
}

export type BlokSoort = AntwoordBlok["soort"];

export interface Antwoord { sjabloon: string; versie: number; blokken: AntwoordBlok[]; doelen: AntwoordVindplaats[] }

export const BLOK_SOORTEN: readonly BlokSoort[] = ["definities", "begrippen", "wettekst", "citaten", "verwijzingen", "annotaties", "toelichting", "twijfel", "extern", "stukken", "leemte"];

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
    case "stukken": return typeof b.kop === "string" &&
      lijst((x) => isObject(x) && typeof x.id === "string" && typeof x.label === "string") &&
      (b.telling == null || (isObject(b.telling) && typeof b.telling.aantal === "number"));
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
export const NIET_GETOETST: readonly BlokSoort[] = ["annotaties", "begrippen", "leemte", "stukken"];

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

type ExternePassage = Extract<AntwoordBlok, { soort: "extern" }>["passages"][number];

/** Een groep passages in het blok `extern`: een alinea, een voetnoot of een tabel (de kop met haar kolommen en de
 *  rijen die eronder vallen). Opeenvolgende tabelrijen horen bij de laatste tabelkop ervoor; tabelrijen zonder kop (een
 *  tabel waarvan Lex alleen rijen aanwees) krijgen een tabel zonder kolomkoppen. */
export type ExternGroep =
  | { soort: "tekst"; passage: ExternePassage }
  | { soort: "voetnoot"; passage: ExternePassage }
  | { soort: "tabel"; kop?: ExternePassage; rijen: ExternePassage[] };

export function externGroepen(passages: readonly ExternePassage[]): ExternGroep[] {
  const uit: ExternGroep[] = [];
  for (const p of passages) {
    const laatste = uit.at(-1);
    if (p.soort === "tabel") uit.push({ soort: "tabel", kop: p, rijen: [] });
    else if (p.soort === "tabelrij") {
      if (laatste?.soort === "tabel") laatste.rijen.push(p);
      else uit.push({ soort: "tabel", rijen: [p] });
    } else uit.push({ soort: p.soort === "voetnoot" ? "voetnoot" : "tekst", passage: p });
  }
  return uit;
}

/** Een stuk uit een gezamenlijke behandeling van dossiers: "gezamenlijk behandeld: 33752–33755", de spiegel van
 *  `gezamenlijk_tekst` in `bronmodel/antwoord.py`. Het veld `gezamenlijk`, niet `reeks`: dat is per connector iets anders. Zonder die zin stonden in de lijst van dossier 33755 tien stukken als
 *  "Kamerstukken 33752, nr. B" zonder uitleg (ronde 2 Kamerstukken, 11 nov 2026). Leeg bij één dossier. */
export function gezamenlijkTekst(reeks: readonly string[] | undefined): string {
  if (!reeks || reeks.length < 2) return "";
  return reeks.length > 2 ? `gezamenlijk behandeld: ${reeks[0]}–${reeks[reeks.length - 1]}` : `gezamenlijk behandeld: ${reeks[0]} en ${reeks[1]}`;
}
