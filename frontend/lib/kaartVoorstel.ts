// De voorstellen van Lex per veld van een begrip (spoor D, fase E): de rekenkern achter
// `KaartVoorstelKaart`, op de begripskaart en in `BegripPaneel`.
//
// Een voorstel van Lex is een eigen object bij de api (`api/app/begrip_voorstel_store.py`), geen
// wijziging: pas *Overnemen* raakt het begrip. Lex vraag je in het gesprek (de begrippen-agent, F3c);
// hier staat wat de werkplek over een voorstel zegt – welk voorstel bij welk veld hoort, hoe de herkomst
// heet, wanneer het verouderd is – zonder DOM, zodat het in vitest te toetsen is.

import { AANDACHTSPUNT } from "@/lib/begripVoorstellen";
import type {
  Begrip, DefinitieOnderbouwing, DefinitieWaarde, Duiding, KaartVeld, KaartVoorstel, TekstWaarde, VindplaatsSoort,
} from "@/lib/types";

/** De codes van graph-qa `kaartacties.TEKST`; `kaartVoorstel.test.ts` leest die bron. */
export const AANDACHTSPUNT_LEX: Record<string, string> = {
  DEFINITIE_VIA_VERWIJZING: "De definitie staat in een regeling waarnaar een begripsbepaling van het werkgebied verwijst; controleer of ze hier geldt.",
  DEFINITIE_ELDERS: "Elders in de graaf gevonden; een verband met het werkgebied is niet aangetoond.",
  GEEN_VERBETERING: "Lex vond geen scherpere definitie dan de huidige.",
  MODEL_ONBRUIKBAAR: "Lex gaf geen bruikbaar antwoord.",
  DOOR_LEX_VERGELEKEN: "De vergelijking is van Lex; toets haar aan de passages van beide begrippen.",
  DOOR_LEX_VOORBEELD: "Dit voorbeeld is door Lex bedacht en heeft geen bronanker; toets het aan de definitie.",
  HERHAALT_DEFINITIE: "Het voorbeeld herhaalt de definitie; het toetst de afbakening niet.",
  GEEN_TEGENVOORBEELD: "Er is geen tegenvoorbeeld; een voorbeeld dat er net buiten valt, toetst de grens.",
  DOOR_LEX_UITLEG: "Deze uitleg is door Lex geschreven; toets haar aan de definitie en de passages.",
  B1_LANGE_ZIN: "Een zin is langer dan 20 woorden; maak er twee zinnen van.",
  B1_TE_LANG: "De uitleg heeft meer dan vijf zinnen; houd het bij één korte alinea.",
  B1_LIJDENDE_VORM: "De uitleg gebruikt een lijdende vorm; zeg wie iets doet.",
  B1_MOEILIJK_WOORD: "De uitleg gebruikt een moeilijk woord waarvoor een gewoner woord bestaat.",
  B1_VAKTERM_ONVERKLAARD: "Een vakterm uit de definitie staat in de uitleg zonder dat die hem uitlegt.",
  B1_HERHAALT_DEFINITIE: "De uitleg herhaalt de definitie; zeg het in eigen, eenvoudige woorden.",
  TOETST_ANDERE_VRAAG: "Dit voorbeeld toetst niet het begrip maar een scenario, voorwaarde of rechtsgevolg; controleer of het de afbakening van de definitie raakt.",
  SEMANTISCH_DUBBEL: "Een voorbeeld toetste hetzelfde kenmerk met hetzelfde oordeel als een ander, alleen met andere getallen of namen; het is weggelaten.",
};

/** De tekst bij een aandachtspunt; een onbekende code verschijnt als zichzelf. */
export function aandachtTekst(code: string): string {
  return AANDACHTSPUNT_LEX[code] ?? AANDACHTSPUNT[code] ?? code;
}

export const PLAATS_LABEL: Record<Exclude<VindplaatsSoort, "">, string> = {
  werkgebied: "in het werkgebied",
  regeling: "in een regeling van het werkgebied",
  definitieverwijzing: "in een regeling waarnaar het werkgebied verwijst",
  elders: "elders in de graaf",
};

export const VERGELIJKING_LABEL: Record<NonNullable<TekstWaarde["vergelijking"]>, string> = {
  zelfde_betekenis: "Zelfde betekenis",
  verwant: "Verwant, maar een ander begrip",
  verschil: "Betekenisverschil",
  onbeslist: "Onbeslist",
};

export const VELD_LABEL: Record<KaartVeld, string> = {
  definitie: "Definitie",
  uitleg: "Uitleg",
  context: "Toelichting",
  voorbeelden: "Voorbeeld",
};

export function isDefinitie(v: KaartVoorstel): v is KaartVoorstel & { waarde: DefinitieWaarde } {
  return v.veld === "definitie";
}

/** "Onderzochte context: 7 bepalingen; ontbreekt: budget: 3; 1 open vraag" (spoor M), of null. */
export function onderzoekTekst(v: KaartVoorstel): string | null {
  const o = v.door?.onderzoek;
  if (!o) return null;
  const delen = [`Onderzochte context: ${o.onderzocht === 1 ? "1 bepaling" : `${o.onderzocht} bepalingen`}`];
  if (o.ontbrekend.length) delen.push(`ontbreekt: ${o.ontbrekend.join(", ")}`);
  if (o.vragen) delen.push(o.vragen === 1 ? "1 open betekenisvraag" : `${o.vragen} open betekenisvragen`);
  return delen.join("; ");
}

const SOORT_LABEL = { begrip: "een begrip", berekeningsresultaat: "een berekeningsresultaat",
  afleidingsregel: "een afleidingsregel", toepassingsgeval: "een toepassingsgeval" } as const;

/** "Lex duidt dit als een toepassingsgeval (specifiek); voorgestelde naam: …", of null zonder duiding. */
export function duidingTekst(v: KaartVoorstel): string | null {
  if (!isDefinitie(v) || !v.waarde.duiding) return null;
  return duidingZin(v.waarde.duiding);
}

/** De duiding in één zin: dezelfde bij het voorstel en, na het overnemen, onder de definitie. */
export function duidingZin(d: Duiding): string {
  let t = `Lex duidt dit als ${SOORT_LABEL[d.soort]} (${d.bereik})`;
  if (d.voorkeursterm) t += `; voorgestelde naam: ${d.voorkeursterm}`;
  return t;
}

/** De kop van de onderbouwing onder een overgenomen definitie: "Letterlijk uit Artikel 2, lid 1 – via een
 *  voorstel van Lex" of "Rust op 2 fragmenten uit de bron – via een betekenisgroep". */
export function onderbouwingKop(o: DefinitieOnderbouwing): string {
  const n = o.fragmenten.length;
  const wat = o.herkomst === "letterlijk" && (o.definitie_vindplaats || o.definitie_bron_iri)
    ? `Letterlijk uit ${o.definitie_vindplaats || o.definitie_bron_iri}`
    : `Rust op ${n === 1 ? "1 fragment" : `${n} fragmenten`} uit de bron`;
  const via = o.voorstel_id ? "via een voorstel van Lex" : o.groep_id ? "via een betekenisgroep" : "";
  return via ? `${wat} – ${via}` : wat;
}

const VOORBEELD_LABEL = { positief: "Positief voorbeeld", tegenvoorbeeld: "Tegenvoorbeeld", grensgeval: "Grensgeval",
  afwijkend: "Afwijkend geval" } as const;

/** "Tegenvoorbeeld · toetst het begrip · kenmerk: een voorlopige aanslag", of null. */
export function voorbeeldTekst(v: KaartVoorstel): string | null {
  if (isDefinitie(v) || v.veld !== "voorbeelden") return null;
  const w = v.waarde as TekstWaarde;
  const delen = [w.soort_voorbeeld ? VOORBEELD_LABEL[w.soort_voorbeeld] : "",
    w.toetst ? `toetst ${w.toetst === "begrip" ? "het begrip" : `een ${w.toetst}`}` : "",
    w.kenmerk ? `kenmerk: ${w.kenmerk}` : ""].filter(Boolean);
  return delen.length ? delen.join(" · ") : null;
}

/** "Letterlijk uit Artikel 2, lid 1, onderdeel m – Invorderingswet 1990" / "Geformuleerd door Lex". */
export function herkomstLabel(v: KaartVoorstel): string {
  if (!isDefinitie(v)) return v.veld === "voorbeelden" ? "Bedacht door Lex" : "Voorgesteld door Lex";
  const w = v.waarde;
  if (w.herkomst === "letterlijk") {
    const plek = w.definitie_vindplaats || w.definitie_bron_iri;
    const waar = w.vindplaats_soort && w.vindplaats_soort !== "werkgebied" ? ` (${PLAATS_LABEL[w.vindplaats_soort]})` : "";
    return `Letterlijk uit ${plek}${waar}`;
  }
  if (w.herkomst === "samengesteld") {
    const n = w.fragmenten.length;
    return `Samengesteld uit de bron (${n === 1 ? "1 fragment" : `${n} fragmenten`})`;
  }
  return "Geformuleerd door Lex";
}

/** Bij het veld definitie op de kaart: wie de bewaarde definitie voorstelde. */
export function definitieDoor(inhoud: Begrip["inhoud"]): string {
  if (!inhoud.definitie?.trim()) return "";
  if (inhoud.definitie_door === "lex") return "Van Lex overgenomen";
  if (inhoud.definitie_door === "analist") return "Door de analist";
  return "";
}

/** De open voorstellen per veld, in de volgorde van de api (nieuwste run eerst, dan de volgorde van Lex). */
export function openPerVeld(voorstellen: readonly KaartVoorstel[]): Record<KaartVeld, KaartVoorstel[]> {
  const uit: Record<KaartVeld, KaartVoorstel[]> = { definitie: [], uitleg: [], context: [], voorbeelden: [] };
  for (const v of voorstellen) if (v.status === "open") uit[v.veld].push(v);
  return uit;
}

/** De tekst die een voorstel draagt, voor het voorstel zelf en voor *Aanpassen*. */
export function voorstelTekst(v: KaartVoorstel): string {
  return isDefinitie(v) ? v.waarde.definitie : (v.waarde as TekstWaarde).tekst;
}

/** De 409 bij een veranderde definitie: wat er stond, wat er staat, wat Lex voorstelde. */
export interface Verouderd {
  voorstelId: string;
  toen: string;
  nu: string;
  voorstel: string;
}

export function verouderdUit(e: unknown, voorstelId: string): Verouderd | null {
  const d = (e as { status?: number; data?: Record<string, unknown> } | null)?.data;
  if ((e as { status?: number })?.status !== 409 || d?.fout !== "voorstel_verouderd") return null;
  const def = (x: unknown) => ((x as { definitie?: string } | undefined)?.definitie ?? "");
  return { voorstelId, toen: def(d.toen), nu: def(d.nu), voorstel: def(d.voorstel) };
}
