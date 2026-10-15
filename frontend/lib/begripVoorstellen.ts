// Rekenkern van de strook "Voorstellen van Lex" (spoor D, levering 3a): volgorde, wat een overname
// wordt, en de woorden waarmee de werkplek de uitkomst van de keten noemt. Puur, voor vitest.

import type {
  Begripstype, Betekenisgroep, DefinitieHerkomst, GroepBesluit, GroepenAntwoord, KaartFragment, ModelOordeelSoort,
  Passage, TwijfelVraag, VerdiepingWerkvoorraad,
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

/** Wat de bevestiging vóór het meedenken toont. */
export interface MeedenkInhoud {
  aantal: number;
  vragen: number;
  kaarten: number;
  /** Batches die al klaar zijn: Lex gaat verder waar hij bleef. */
  alKlaar: number;
  schatting: number | null;
  schattingUitleg: string;
  budgetOver: number | null;
  budgetKrap: boolean;
}

export function meedenkInhoud(wv: VerdiepingWerkvoorraad): MeedenkInhoud {
  const schatting = wv.schatting?.totaal ?? null;
  const budgetOver = wv.budget?.actief ? wv.budget.resterend : null;
  return {
    aantal: wv.aantal, vragen: wv.vragen.length, kaarten: wv.kaarten.length, alKlaar: wv.batches.length,
    schatting, schattingUitleg: wv.schatting_toelichting ?? "",
    budgetOver, budgetKrap: schatting !== null && budgetOver !== null && schatting > budgetOver,
  };
}

/** "3 twijfelpunten en 2 begrippen zonder definitie". */
export function meedenkOmvang(i: Pick<MeedenkInhoud, "vragen" | "kaarten">): string {
  const delen = [
    i.vragen ? `${i.vragen} ${i.vragen === 1 ? "twijfelpunt" : "twijfelpunten"}` : "",
    i.kaarten ? `${i.kaarten} ${i.kaarten === 1 ? "begrip" : "begrippen"} zonder definitie` : "",
  ].filter(Boolean);
  return delen.join(" en ") || "niets";
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

/** De relaties van de keten in gewone woorden: "X geldt als Y". */
export const HYPOTHESE_LABEL: Record<string, string> = {
  zelfde_betekenis: "betekent hetzelfde als",
  kwalificatie: "geldt als",
  inclusie: "omvat ook",
  uitsluiting: "omvat niet",
  hierarchie: "is een soort",
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

/** Een statusregel van graph-qa ("Lex · Groeperen: …") zonder de actor, voor de voortgangslijst. */
export function voortgangsregel(bericht: string): string {
  return bericht.replace(/^Lex\s*·\s*/, "");
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
