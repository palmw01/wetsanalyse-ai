// Rekenkern van de strook "Voorstellen van Lex" (spoor D, levering 3a): volgorde, wat een overname
// wordt, en de woorden waarmee de werkplek de uitkomst van de keten noemt. Puur, voor vitest.

import { klasseLabel } from "./jas";
import type {
  Aanpassing, AkkoordInvoer, Begrip, Begripstype, Betekenisgroep, DefinitieHerkomst, GroepBesluit, GroepenAntwoord,
  KaartFragment, Koppeling, ModelOordeelSoort, Passage, TwijfelVraag,
} from "./types";

/** De vraag die in het gesprek komt te staan; graph-qa herkent hem ook zonder `modus` (fase C). */
export const MEEDENK_PROMPT = "Denk mee over de begrippen";

export const HERKOMST_LABEL: Record<DefinitieHerkomst, string> = {
  letterlijk: "letterlijk uit de wet",
  samengesteld: "samengesteld uit de bron",
  geformuleerd: "geformuleerd door Lex",
};

/** Het advies van Lex bij een twijfelvraag, in gewone woorden. */
export const OORDEEL_LABEL: Record<ModelOordeelSoort, string> = {
  zelfde_betekenis: "hetzelfde begrip",
  verwant_ander_begrip: "verwant, maar een ander begrip",
  betekenisverschil: "andere betekenis",
  onbeslist: "geen uitsluitsel",
};

export const BEGRIPSTYPE_LABEL: Record<Begripstype, string> = {
  entiteit: "entiteit", actor: "actor", toestand: "toestand", gebeurtenis: "gebeurtenis",
  eigenschap: "eigenschap", relatie: "relatie",
};

/** De aandachtspunten van een concept-kaart – dezelfde codes en teksten als graph-qa
 *  `begrippen_pipeline/toetsen.py` (`TEKST`); `begripVoorstellen.test.ts` bewaakt dat. */
export const AANDACHTSPUNT: Record<string, string> = {
  FRAGMENT_ONBEKEND: "De definitie noemt een fragment dat niet in het manifest bestaat.",
  FRAGMENT_NIET_LETTERLIJK: "Een fragment staat niet letterlijk op zijn plek in de bron.",
  LETTERLIJK_NIET_IN_BRON: "De 'letterlijke' definitie staat niet zo in haar bron.",
  SAMENGESTELD_NIET_UIT_FRAGMENTEN: "De samengestelde definitie is meer dan haar fragmenten.",
  CIRCULAIR: "De definitie gebruikt de naam van het begrip zelf.",
  REKENREGEL: "Dit leest als een rekenregel of hoeveelheid, niet als een definitie.",
  GEMENGDE_KLASSEN: "De passages hebben verschillende JAS-klassen; controleer of het één begrip is.",
  GEEN_BEGRIP: "De passages zijn tijdsaanduidingen, parameters of operatoren; dat is meestal geen begrip.",
  GEEN_DEFINITIE: "Er is nog geen definitie voorgesteld.",
  MODEL_GEEN_DEFINITIE: "Lex gaf voor deze groep geen bruikbare definitie.",
  CIRCULAIR_VERWORPEN: "Lex formuleerde een definitie met de naam van het begrip zelf; die is niet overgenomen.",
  DOOR_LEX_GEFORMULEERD: "De definitie is door Lex geformuleerd; toets haar aan de passages.",
};

/** De aandachtspunten om te tonen: "geen definitie" naast "Lex gaf geen definitie" zegt twee keer
 *  hetzelfde. Een onbekende code blijft zichtbaar als code. */
export function aandachtspunten(codes: readonly string[]): string[] {
  const dubbel = codes.includes("MODEL_GEEN_DEFINITIE") || codes.includes("CIRCULAIR_VERWORPEN");
  return codes.filter((c) => !(dubbel && c === "GEEN_DEFINITIE")).map((c) => AANDACHTSPUNT[c] ?? c);
}

/** De definitie van een groep: uit de kaart als die er is (fase C), anders de letterlijke van de keten. */
export interface GroepDefinitie {
  tekst: string;
  herkomst: DefinitieHerkomst;
  vindplaats: string;
  fragmenten: KaartFragment[];
}

export function groepDefinitie(g: Betekenisgroep): GroepDefinitie | null {
  const k = g.kaart;
  if (k?.definitie && k.herkomst)
    return { tekst: k.definitie, herkomst: k.herkomst, vindplaats: k.definitie_vindplaats, fragmenten: k.fragmenten };
  if (g.voorstel.definitie)
    return { tekst: g.voorstel.definitie, herkomst: "letterlijk", vindplaats: g.voorstel.definitie_vindplaats ?? "", fragmenten: [] };
  return null;
}

/** De twijfelvragen die nog een antwoord vragen: na de verdieping alleen de vragen die open bleven. */
export function openVragen(data: GroepenAntwoord | null): TwijfelVraag[] {
  const vragen = data?.run?.uitkomst?.vragen ?? [];
  const open = data?.verdieping?.vragen_open;
  return open ? vragen.filter((v) => open.includes(v.kandidaat_id)) : vragen;
}

/** Groen: de wet legt het verband zelf (een definitie, "bedoeld in"). Geel: er is ook iets dat
 *  ertegen pleit; de jurist beslist. Kleur draagt het nooit alleen. */
export const AANDACHT_LABEL: Record<"groen" | "geel", string> = {
  groen: "door de wet onderbouwd",
  geel: "vraagt een oordeel",
};

export const BESLUIT_LABEL: Record<GroepBesluit, string> = {
  open: "open",
  overgenomen: "overgenomen",
  gekoppeld: "gekoppeld aan een begrip",
  afgewezen: "afgewezen",
  geparkeerd: "geparkeerd",
};

const OPEN = (g: Betekenisgroep) => g.besluit === "open" || g.besluit === "geparkeerd";

/** Wat nog een besluit vraagt eerst (open, dan geparkeerd), daarbinnen geel vóór groen en meer leden
 *  eerst; besloten groepen achteraan. Stabiel op naam. */
export function sorteerGroepen(groepen: readonly Betekenisgroep[]): Betekenisgroep[] {
  const rang = (g: Betekenisgroep) => (g.besluit === "open" ? 0 : g.besluit === "geparkeerd" ? 1 : 2);
  return [...groepen].sort(
    (a, b) =>
      rang(a) - rang(b) ||
      (a.aandacht === b.aandacht ? 0 : a.aandacht === "geel" ? -1 : 1) ||
      b.leden.length - a.leden.length ||
      a.voorstel.naam.localeCompare(b.voorstel.naam, "nl"),
  );
}

export const isBeslisbaar = OPEN;

/** De overname voor de api: één of meer groepen, met de gekozen leden. Zijn alle leden gekozen, dan
 *  hoeven ze niet mee (de api neemt dan de hele groep); is het een deel, dan is het splitsen. */
export function overnameVoor(
  groepen: readonly Betekenisgroep[],
  gekozen: ReadonlySet<string>,
  naam: string,
  metDefinitie: boolean,
): { groep_ids: string[]; naam: string; element_ids?: string[]; met_definitie: boolean } {
  const alle = groepen.flatMap((g) => g.leden.map((l) => l.element_id));
  const leden = alle.filter((e) => gekozen.has(e));
  return {
    groep_ids: groepen.map((g) => g.id),
    naam: naam.trim(),
    ...(leden.length === alle.length ? {} : { element_ids: leden }),
    met_definitie: metDefinitie,
  };
}

/** De definitie die mee kan bij een overname: alleen als er precies één is (bij combineren kiest de
 *  analist zelf, zo doet de api het ook). Uit de kaart als die er is, anders de letterlijke. */
export function enigeDefinitie(groepen: readonly Betekenisgroep[]): GroepDefinitie | null {
  const defs = new Map<string, GroepDefinitie>();
  for (const g of groepen) {
    const d = groepDefinitie(g);
    if (d) defs.set(`${d.herkomst}\u0000${d.tekst}`, d);
  }
  return defs.size === 1 ? [...defs.values()][0] : null;
}

/** De groepen waar beide passages van een twijfelvraag in staan en die nog open zijn – die zet
 *  "samen" klaar om te combineren. */
export function groepenVanVraag(vraag: TwijfelVraag, groepen: readonly Betekenisgroep[]): string[] {
  const in_ = (e: string) => groepen.find((g) => OPEN(g) && g.leden.some((l) => l.element_id === e))?.id;
  const ids = [in_(vraag.van), in_(vraag.naar)].filter((x): x is string => !!x);
  return [...new Set(ids)];
}

/** Een passage in één regel: "“tekst” (vindplaats)". Ontbreekt hij, dan het id – liever zichtbaar
 *  onbekend dan stil weg. */
export function passageTekst(e: string, passages: Record<string, Passage>, groepen: readonly Betekenisgroep[] = []): string {
  const p = passages[e] ?? groepen.flatMap((g) => g.leden).find((l) => l.element_id === e);
  return p ? `“${p.tekst}”${p.vindplaats ? ` (${p.vindplaats})` : ""}` : e;
}


/** "Samen" bij een twijfelvraag wordt één begrip: beide passages, plus de leden van een open groep
 *  waar een van de twee in zit. De naam: die van zo'n groep, anders de tekst van de eerste passage. */
export function samenOvername(
  vraag: TwijfelVraag,
  groepen: readonly Betekenisgroep[],
  passages: Record<string, Passage>,
): { groep_ids: string[]; naam: string; element_ids: string[]; met_definitie: boolean } {
  const ids = groepenVanVraag(vraag, groepen);
  const gekozen = groepen.filter((g) => ids.includes(g.id));
  const leden = [...new Set([...gekozen.flatMap((g) => g.leden.map((l) => l.element_id)), vraag.van, vraag.naar])];
  const tekst = passages[vraag.van]?.tekst ?? groepen.flatMap((g) => g.leden).find((l) => l.element_id === vraag.van)?.tekst ?? "";
  const naam = gekozen[0]?.voorstel.naam ?? tekst.replace(/^(de|het|een|die|deze|dat|dit)\s+/i, "").toLowerCase();
  return { groep_ids: ids, naam, element_ids: leden, met_definitie: true };
}

// --- De review (fase D): één lijst met groepen en twijfelvragen, zoals de annotatiereview ---------

export type ReviewFilter = "te_beoordelen" | "aandacht" | "alles";

export const REVIEW_FILTERS: { waarde: ReviewFilter; label: string }[] = [
  { waarde: "te_beoordelen", label: "Te beoordelen" },
  { waarde: "aandacht", label: "Aandacht" },
  { waarde: "alles", label: "Alles" },
];

export type ReviewItem =
  | { soort: "groep"; id: string; groep: Betekenisgroep }
  | { soort: "vraag"; id: string; vraag: TwijfelVraag };

/** Een groep is beoordeeld zodra er een besluit is; parkeren telt mee (het is een keuze), en een
 *  gesplitste groep met een rest is nog open. */
const groepBeslist = (g: Betekenisgroep) => g.besluit !== "open";

function vraagBeslist(v: TwijfelVraag, data: GroepenAntwoord | null): boolean {
  return !!data?.run?.vragen_besluiten?.[v.kandidaat_id];
}

/** De items in de volgorde van de review: open gele groepen, de open twijfelvragen, open groene
 *  groepen; daarna wat al een besluit heeft (alleen bij "alles"). Het toetsenbord loopt precies deze
 *  volgorde door. */
export function reviewItems(data: GroepenAntwoord | null, filter: ReviewFilter): ReviewItem[] {
  const groepen = sorteerGroepen(data?.groepen ?? []);
  const vragen = openVragen(data);
  const g = (x: Betekenisgroep): ReviewItem => ({ soort: "groep", id: x.id, groep: x });
  const v = (x: TwijfelVraag): ReviewItem => ({ soort: "vraag", id: x.kandidaat_id, vraag: x });
  const openG = groepen.filter((x) => !groepBeslist(x));
  const openV = vragen.filter((x) => !vraagBeslist(x, data));
  const open = [...openG.filter((x) => x.aandacht === "geel").map(g), ...openV.map(v),
    ...openG.filter((x) => x.aandacht !== "geel").map(g)];
  if (filter === "te_beoordelen") return open;
  if (filter === "aandacht") return open.filter((i) => i.soort === "vraag" || i.groep.aandacht === "geel");
  return [...open, ...groepen.filter(groepBeslist).map(g), ...vragen.filter((x) => vraagBeslist(x, data)).map(v)];
}

/** "4/11 beoordeeld": groepen en twijfelvragen samen. */
export function reviewVoortgang(data: GroepenAntwoord | null): { totaal: number; beslist: number; aandacht: number } {
  const groepen = data?.groepen ?? [];
  const vragen = openVragen(data);
  const openG = groepen.filter((g) => !groepBeslist(g));
  return {
    totaal: groepen.length + vragen.length,
    beslist: groepen.filter(groepBeslist).length + vragen.filter((v) => vraagBeslist(v, data)).length,
    aandacht: openG.filter((g) => g.aandacht === "geel").length + vragen.filter((v) => !vraagBeslist(v, data)).length,
  };
}

/** Het volgende (of vorige) item; zonder selectie het eerste (of laatste). */
export function volgendeItem(items: readonly ReviewItem[], actiefId: string | undefined, richting: 1 | -1): ReviewItem | undefined {
  if (!items.length) return undefined;
  const i = items.findIndex((x) => x.id === actiefId);
  if (i < 0) return richting === 1 ? items[0] : items[items.length - 1];
  return items[i + richting];
}

/** Na een besluit door naar het volgende item dat nog open is – zoals `a` bij annoteren. */
export function naBesluit(itemsVoor: readonly ReviewItem[], beslotenId: string, itemsNa: readonly ReviewItem[]): string | undefined {
  const plek = itemsVoor.findIndex((x) => x.id === beslotenId);
  const daarna = itemsVoor.slice(plek + 1).map((x) => x.id);
  const nogOpen = new Set(itemsNa.map((x) => x.id));
  return daarna.find((id) => nogOpen.has(id)) ?? itemsNa.find((x) => x.id !== beslotenId)?.id;
}

/** Wat de akkoordknop belooft: de poort vooraf zegt of het een geaccordeerd begrip wordt. */
export function akkoordLabel(g: Betekenisgroep): { label: string; concept: boolean; redenen: string[] } {
  const p = g.poort_vooraf;
  if (!p || p.mag) return { label: "Akkoord", concept: false, redenen: [] };
  const n = p.redenen.length;
  return { label: `Akkoord als concept (${n} ${n === 1 ? "open punt" : "open punten"})`, concept: true, redenen: p.redenen };
}

/** Het akkoord voor de api. Zijn alle leden gekozen, dan hoeven ze niet mee (de api neemt de rest van
 *  de groepen); is het een deel, dan is het splitsen. */
export function akkoordVoor(
  groepen: readonly Betekenisgroep[],
  gekozen: ReadonlySet<string>,
  naam: string,
  opties: { aanpassing?: Aanpassing; definitieVan?: string; metDefinitie?: boolean } = {},
): AkkoordInvoer {
  const o = overnameVoor(groepen, gekozen, naam, opties.metDefinitie ?? true);
  return {
    ...o,
    ...(opties.aanpassing && Object.keys(opties.aanpassing).length ? { aanpassing: opties.aanpassing } : {}),
    ...(opties.definitieVan ? { definitie_van: opties.definitieVan } : {}),
  };
}

/** "Samen" bij een twijfelvraag als akkoord: beide passages plus de open groepen waar ze in staan; de
 *  vraag wordt met hetzelfde akkoord beantwoord. */
export function samenAkkoord(
  vraag: TwijfelVraag, groepen: readonly Betekenisgroep[], passages: Record<string, Passage>, naam?: string,
): AkkoordInvoer {
  const o = samenOvername(vraag, groepen, passages);
  return { ...o, naam: (naam ?? o.naam).trim(), kandidaat_id: vraag.kandidaat_id };
}

/** Alleen wat de jurist echt veranderde gaat als aanpassing mee: een ongewijzigd veld laat de api het
 *  voorstel gebruiken (en de herkomst staan). */
export function aanpassingUit(
  voorstel: { definitie: string; herkomst: DefinitieHerkomst | null; context: string; begripstype: Begripstype | "" },
  invoer: { definitie: string; herkomst: DefinitieHerkomst | null; context: string; begripstype: Begripstype | "" },
): Aanpassing {
  const a: Aanpassing = {};
  if (invoer.definitie.trim() !== voorstel.definitie.trim()) a.definitie = invoer.definitie.trim();
  if (invoer.herkomst && invoer.herkomst !== voorstel.herkomst) {
    a.definitie_herkomst = invoer.herkomst;
    if (a.definitie === undefined) a.definitie = invoer.definitie.trim();
  }
  if (invoer.context.trim() !== voorstel.context.trim()) a.context = invoer.context.trim();
  if (invoer.begripstype !== voorstel.begripstype) a.begripstype = invoer.begripstype;
  return a;
}

/** De herkomst na een aanpassing, zoals de api haar zet: een andere tekst is `geformuleerd`, behalve
 *  als de jurist `letterlijk` kiest (de api toetst dan of de tekst zo in de bron staat). */
export function herkomstNaAanpassing(oud: { tekst: string; herkomst: DefinitieHerkomst | null }, tekst: string,
  gekozen: DefinitieHerkomst | null): DefinitieHerkomst | null {
  if (!tekst.trim()) return null;
  if (gekozen === "letterlijk") return "letterlijk";
  if (tekst.trim() !== oud.tekst.trim() || gekozen === "geformuleerd" || !oud.herkomst) return "geformuleerd";
  return oud.herkomst;
}

/** Wat combineren naast elkaar zet, met de signalen die ertegen pleiten (PLAN §D: combineren toont
 *  eerst een vergelijking). Een signaal is geen verbod. */
export interface Vergelijking {
  groepen: { id: string; naam: string; definitie: GroepDefinitie | null; begripstype: Begripstype | null;
    klassen: string[]; leden: Passage[]; aandacht: "groen" | "geel" }[];
  signalen: string[];
  /** Groepen met een definitie: daaruit kiest de jurist er één (of geen). */
  metDefinitie: string[];
}

export function vergelijk(groepen: readonly Betekenisgroep[]): Vergelijking {
  const rijen = groepen.map((g) => ({
    id: g.id, naam: g.voorstel.naam, definitie: groepDefinitie(g), begripstype: g.kaart?.begripstype ?? null,
    klassen: [...new Set(g.leden.map((l) => klasseLabel(l.jas_klasse)))], leden: g.leden, aandacht: g.aandacht,
  }));
  const signalen: string[] = [];
  const typen = new Set(rijen.map((r) => r.begripstype).filter(Boolean));
  if (typen.size > 1) signalen.push(`Verschillende begripstypen: ${[...typen].map((t) => BEGRIPSTYPE_LABEL[t!]).join(", ")}.`);
  const klassen = new Set(rijen.flatMap((r) => r.klassen));
  if (klassen.size > 1) signalen.push(`Verschillende JAS-klassen: ${[...klassen].join(", ")}.`);
  const defs = new Set(rijen.map((r) => r.definitie?.tekst).filter(Boolean));
  if (defs.size > 1) signalen.push("De groepen hebben elk een eigen definitie; kies er één, of geen.");
  const conflicten = groepen.reduce((n, g) => n + g.conflicten.length, 0);
  if (conflicten) signalen.push(`Lex zag ${conflicten === 1 ? "één aanwijzing" : `${conflicten} aanwijzingen`} dat passages níét hetzelfde betekenen.`);
  return { groepen: rijen, signalen, metDefinitie: rijen.filter((r) => r.definitie).map((r) => r.id) };
}

/** De dragende passages van een concept waarvan de annotatie nog niet door een jurist is beoordeeld:
 *  daar staat in de review de knop "Annotatie akkoord". */
export function onbeoordeeldeAnnotaties(b: Begrip): Koppeling[] {
  return b.koppelingen.filter((k) => (k.rol === "duiding" || k.rol === "definitie") && k.beoordeling !== "afgewezen"
    && k.actualiteit === "actueel" && !k.annotatie_beoordeeld);
}
