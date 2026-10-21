// De voorstellen van Lex per veld van een begrip (spoor D, fase E): de rekenkern achter
// `KaartVoorstelKaart`, op de begripskaart en in `BegripPaneel`.
//
// Een voorstel van Lex is een eigen object bij de api (`api/app/begrip_voorstel_store.py`), geen
// wijziging: pas *Overnemen* raakt het begrip. Lex vraag je in het gesprek (de begrippen-agent, F3c);
// hier staat wat de werkplek over een voorstel zegt – welk voorstel bij welk veld hoort, hoe de herkomst
// heet, wanneer het verouderd is – zonder DOM, zodat het in vitest te toetsen is.

import { AANDACHTSPUNT } from "@/lib/begripVoorstellen";
import type { Begrip, DefinitieWaarde, KaartVeld, KaartVoorstel, TekstWaarde, VindplaatsSoort } from "@/lib/types";

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
  open_vragen: "Open vraag",
  voorbeelden: "Voorbeeld",
};

export function isDefinitie(v: KaartVoorstel): v is KaartVoorstel & { waarde: DefinitieWaarde } {
  return v.veld === "definitie";
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
  const uit: Record<KaartVeld, KaartVoorstel[]> = { definitie: [], uitleg: [], open_vragen: [], voorbeelden: [] };
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
