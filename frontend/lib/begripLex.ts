// Lex naast de kaart (spoor D, fase E): de rekenkern achter de strook *Lex* en de voorstellen per veld.
//
// Een voorstel van Lex is een eigen object bij de api (`api/app/begrip_voorstel_store.py`), geen
// wijziging: pas *Overnemen* raakt het begrip. Hier staat wat de werkplek erover zegt – welke acties er
// zijn en wanneer ze kunnen, welk voorstel bij welk veld hoort, hoe de herkomst heet – zonder DOM, zodat
// het in vitest te toetsen is.

import { AANDACHTSPUNT } from "@/lib/begripVoorstellen";
import type {
  Begrip, BegripSamenvatting, DefinitieWaarde, KaartActie, KaartRun, KaartVeld, KaartVoorstel,
  KaartVoorstellenAntwoord, TekstWaarde, VindplaatsSoort,
} from "@/lib/types";

export interface ActieInfo {
  actie: KaartActie;
  label: string;
  uitleg: string;
  /** Kost tokens: de knop toont schatting en budget. */
  model: boolean;
}

export const ACTIES: readonly ActieInfo[] = [
  { actie: "brondefinitie", label: "Zoek de brondefinitie", model: false,
    uitleg: "Zoekt in de graaf waar de wet deze term definieert; zonder model." },
  { actie: "scherper", label: "Stel een scherpere definitie voor", model: true,
    uitleg: "Lex stelt een definitie voor op grond van de passages en de bron." },
  { actie: "betekenisverschil", label: "Verklaar het betekenisverschil", model: true,
    uitleg: "Lex vergelijkt dit begrip met een ander begrip uit het werkgebied." },
  { actie: "voorbeelden", label: "Bedenk voorbeelden", model: true,
    uitleg: "Lex bedenkt gevallen die de afbakening toetsen, ook grensgevallen en tegenvoorbeelden." },
];

/** De codes van graph-qa `kaartacties.TEKST`; `begripLex.test.ts` leest die bron. */
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

export const BESLUIT_LABEL: Record<KaartVoorstel["status"], string> = {
  open: "Open",
  overgenomen: "Overgenomen",
  aangepast: "Aangepast overgenomen",
  afgewezen: "Afgewezen",
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

export function besloten(voorstellen: readonly KaartVoorstel[]): KaartVoorstel[] {
  return voorstellen.filter((v) => v.status !== "open");
}

/** De tekst die een voorstel draagt, voor het voorstel zelf en voor *Aanpassen*. */
export function voorstelTekst(v: KaartVoorstel): string {
  return isDefinitie(v) ? v.waarde.definitie : (v.waarde as TekstWaarde).tekst;
}

/** De passages waar Lex op voortbouwt: dragend, niet afgewezen en actueel – zoals de api ze meegeeft. */
export function dragendePassages(begrip: Begrip): number {
  return begrip.koppelingen.filter((k) => (k.rol === "duiding" || k.rol === "definitie")
    && k.beoordeling !== "afgewezen" && k.actualiteit === "actueel").length;
}

/** Waarom een actie nu niet kan, of `null` als ze kan. De api toetst hetzelfde (409/422). */
export function waaromNiet(
  actie: KaartActie, begrip: Begrip, opties: { onbewaard: boolean; ander?: string; budgetOp?: boolean },
): string | null {
  if (opties.onbewaard) return "Sla eerst je wijzigingen op: Lex werkt op het bewaarde begrip.";
  const model = ACTIES.find((a) => a.actie === actie)?.model;
  if (model && opties.budgetOp) return "Je tokenbudget voor deze periode is op.";
  if (actie === "voorbeelden" && !begrip.inhoud.definitie?.trim())
    return "Voorbeelden toetsen een definitie; geef het begrip eerst een definitie.";
  if ((actie === "scherper" || actie === "betekenisverschil") && dragendePassages(begrip) === 0)
    return "Dit begrip heeft nog geen actuele passage die het draagt; daar kan Lex niets op baseren.";
  if (actie === "betekenisverschil" && !opties.ander) return "Kies het begrip om mee te vergelijken.";
  return null;
}

/** "~1.200 tokens" voor een model-actie met een schatting, anders leeg. */
export function schattingTekst(actie: KaartActie, data: KaartVoorstellenAntwoord | null): string {
  const s = data?.schatting?.[actie];
  if (!s || !ACTIES.find((a) => a.actie === actie)?.model) return "";
  return `~${s.tokens.toLocaleString("nl-NL")} tokens`;
}

/** Wat de laatste run van een actie te melden heeft: waarom er niets kwam, of waarom het mislukte. */
export function runMelding(run: KaartRun | undefined): { soort: "uitleg" | "fout"; tekst: string } | null {
  if (!run) return null;
  if (run.status === "mislukt") return { soort: "fout", tekst: run.reden || "Lex kon dit niet afmaken." };
  if (run.status === "klaar" && run.melding) return { soort: "uitleg", tekst: run.melding };
  return null;
}

/** De andere begrippen om mee te vergelijken; wie passages deelt of op de naam lijkt, eerst. */
export function vergelijkKandidaten(begrip: Begrip, andere: readonly BegripSamenvatting[]): BegripSamenvatting[] {
  const eigen = new Set(begrip.koppelingen.map((k) => k.element_id));
  const woorden = (b: { inhoud: { naam: string; alternatieve_termen?: string[] } }) =>
    new Set([b.inhoud.naam, ...(b.inhoud.alternatieve_termen ?? [])].join(" ").toLowerCase().split(/\s+/).filter((w) => w.length > 2));
  const mijn = woorden(begrip);
  const score = (b: BegripSamenvatting) =>
    b.element_ids.filter((e) => eigen.has(e)).length * 10 + [...woorden(b)].filter((w) => mijn.has(w)).length;
  return andere.filter((b) => b.id !== begrip.id)
    .map((b) => ({ b, s: score(b) }))
    .sort((x, y) => y.s - x.s || x.b.inhoud.naam.localeCompare(y.b.inhoud.naam, "nl"))
    .map((x) => x.b);
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
