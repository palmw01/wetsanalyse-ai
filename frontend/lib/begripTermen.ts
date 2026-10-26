// Het begrippenkader per term (spoor H4). De begrippenketen maakt één betekenisgroep per term per bronnode
// (`begrippen_pipeline/groeperen.py`): zeven bepalingen met "tijdvak" geven zeven groepen "tijdvak", en de
// twijfelvragen zijn de vragen of die groepen bij elkaar horen. Hier komen ze weer samen onder hun term,
// met de bestaande begrippen van die naam. Zuiver, zodat vitest het zonder DOM toetst.

import { openVragen } from "./begripVoorstellen";
import type { Betekenisgroep, GroepenAntwoord, Passage, TwijfelVraag } from "./types";

const LIDWOORD = /^(de|het|een)\s+/;

/** Dezelfde normalisatie als de api (`begrippen_run_store._norm`): kleine letters, zonder lidwoord. */
export function normTerm(s: string): string {
  return s.trim().toLowerCase().replace(LIDWOORD, "");
}

export function groepNaam(g: Pick<Betekenisgroep, "kaart" | "voorstel">): string {
  return g.kaart?.naam || g.voorstel.naam;
}

export interface Term {
  sleutel: string;
  /** Hoe de term in beeld heet: de naam van de grootste groep. */
  naam: string;
  /** Groepen die nog een besluit vragen (open of geparkeerd), grootste eerst. */
  open: Betekenisgroep[];
  besloten: Betekenisgroep[];
  /** Twijfelvragen tussen groepen van deze term: met één begrip zijn ze beantwoord. */
  vragenBinnen: TwijfelVraag[];
  /** Twijfelvragen naar een passage van een andere term (of buiten elke groep). */
  vragenBuiten: TwijfelVraag[];
  /** Bestaande begrippen waar de open groepen op lijken (`lijkt_op` van de api), zonder dubbelen. */
  lijktOp: { begrip_id: string; naam: string }[];
  passages: number;
  regelingen: string[];
}

/** De regeling uit een vindplaats "Artikel 9 · Lid 1 – Invorderingswet 1990". */
export function regelingVan(p: Pick<Passage, "vindplaats">): string {
  const i = p.vindplaats.lastIndexOf(" – ");
  return i > 0 ? p.vindplaats.slice(i + 3).trim() : "";
}

const OPEN = (g: Betekenisgroep) => g.besluit === "open" || g.besluit === "geparkeerd";

/** De termen van een ronde van Lex: alleen termen met iets open, of met een besluit in deze ronde; de
 *  meeste open passages eerst, dan op naam. */
export function termenVan(data: GroepenAntwoord | null): Term[] {
  if (!data) return [];
  const perSleutel = new Map<string, Betekenisgroep[]>();
  for (const g of data.groepen) {
    const k = normTerm(groepNaam(g));
    perSleutel.set(k, [...(perSleutel.get(k) ?? []), g]);
  }
  // Van welke term is een passage? (Een vraag verwijst naar elementen, niet naar groepen.) Alleen open
  // groepen tellen: een vraag naar een afgewezen of overgenomen voorstel valt anders weg in een term
  // zonder iets te beoordelen.
  const termVan = new Map<string, string>();
  for (const [k, gs] of perSleutel) for (const g of gs.filter(OPEN)) for (const l of g.leden) termVan.set(l.element_id, k);
  const beantwoord = data.run?.vragen_besluiten ?? {};
  const vragen = openVragen(data).filter((v) => !beantwoord[v.kandidaat_id]);
  const termen: Term[] = [];
  for (const [sleutel, gs] of perSleutel) {
    const open = gs.filter(OPEN).sort((a, b) => b.leden.length - a.leden.length);
    const besloten = gs.filter((g) => !OPEN(g));
    const leden = open.flatMap((g) => g.leden);
    const binnen = vragen.filter((v) => termVan.get(v.van) === sleutel && termVan.get(v.naar) === sleutel);
    const buiten = vragen.filter((v) => (termVan.get(v.van) === sleutel) !== (termVan.get(v.naar) === sleutel)
      && (termVan.get(v.van) === sleutel || termVan.get(v.naar) === sleutel));
    termen.push({
      sleutel,
      naam: groepNaam(open[0] ?? gs[0]),
      open, besloten, vragenBinnen: binnen, vragenBuiten: buiten,
      lijktOp: [...new Map(open.flatMap((g) => g.lijkt_op).map((b) => [b.begrip_id, { begrip_id: b.begrip_id, naam: b.naam }])).values()],
      passages: leden.length,
      regelingen: [...new Set(leden.map(regelingVan).filter(Boolean))].sort((a, b) => a.localeCompare(b, "nl")),
    });
  }
  return termen.sort((a, b) => b.passages - a.passages || a.naam.localeCompare(b.naam, "nl"));
}

/** De open twijfelvragen die bij geen term horen: geen van beide passages staat (nog) in een open groep,
 *  bijvoorbeeld omdat beide kanten al een begrip werden. Het kader toont ze apart, zodat er geen vraag
 *  uit beeld verdwijnt. */
export function losseVragen(data: GroepenAntwoord | null, termen: readonly Term[]): TwijfelVraag[] {
  if (!data) return [];
  const bij = new Set(termen.flatMap((t) => [...t.vragenBinnen, ...t.vragenBuiten]).map((v) => v.kandidaat_id));
  const beantwoord = data.run?.vragen_besluiten ?? {};
  return openVragen(data).filter((v) => !bij.has(v.kandidaat_id) && !beantwoord[v.kandidaat_id]);
}

/** De term bij een sleutel uit de URL (die is genormaliseerd, maar normaliseer voor de zekerheid). */
export function termVan(termen: readonly Term[], sleutel: string): Term | undefined {
  const k = normTerm(sleutel);
  return termen.find((t) => t.sleutel === k);
}

/** Eén begrip van de gekozen passages van een term: de groepen waar ze in staan, en de twijfelvragen
 *  waarvan beide passages gekozen zijn – die gaan in hetzelfde akkoord als *samen* mee (`kandidaat_ids`). */
export function termAkkoord(t: Term, gekozen: ReadonlySet<string>, vragen: readonly TwijfelVraag[]): {
  groepen: Betekenisgroep[]; kandidaat_ids: string[];
} {
  return {
    groepen: t.open.filter((g) => g.leden.some((l) => gekozen.has(l.element_id))),
    kandidaat_ids: vragen.filter((v) => gekozen.has(v.van) && gekozen.has(v.naar)).map((v) => v.kandidaat_id),
  };
}

/** Wat standaard is aangevinkt: alle passages van de open groepen; wat je voor later bewaarde niet. */
export function standaardKeuze(t: Term): Set<string> {
  return new Set(t.open.filter((g) => g.besluit === "open").flatMap((g) => g.leden.map((l) => l.element_id)));
}

/** "3 voorstellen in 2 regelingen", of de naam van de ene regeling. */
export function termOmvang(t: Pick<Term, "open" | "regelingen">): string {
  const n = t.open.length;
  const v = `${n} ${n === 1 ? "voorstel" : "voorstellen"}`;
  if (!t.regelingen.length) return v;
  return t.regelingen.length === 1 ? `${v} · ${t.regelingen[0]}` : `${v} in ${t.regelingen.length} regelingen`;
}
