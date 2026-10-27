// De bronnen van een werkgebied, getoond per deelvraag (spoor K, methode 1f/1g): één bronselectie voor het
// werkgebied, die per deelvraag gekoppeld is. Een bron bij meer deelvragen staat onder elk; wat bij geen
// actieve deelvraag hoort, staat onder *Zonder deelvraag*. Zonder deelvragen is er één groep.
//
// Pure functies, zodat vitest ze zonder DOM toetst (lib/bronnenPerDeelvraag.test.ts).

import type { BronselectieOverzicht } from "./bronselectie";
import type { BronRol, Bronselectie, Deelvraag } from "./types";

export interface BronInGroep {
  selectie: Bronselectie;
  /** De rol bij déze deelvraag (die van de selectie als de deelvraag geen eigen rol heeft). */
  rol: BronRol;
  /** De nummers van de andere actieve deelvragen waar deze bron ook bij hoort. */
  ook: number[];
}

/** Een voorstel van Lex bij een deelvraag dat nog open staat: in de lijst als *Ter beoordeling*. */
export interface VoorstelInGroep { id: string; bron_iri: string; label: string }

export interface BronGroep {
  deelvraag: { id: string; nr: number; vraag: string } | null;
  bronnen: BronInGroep[];
  voorstellen: VoorstelInGroep[];
}

/** Groepeer de bronselecties per actieve deelvraag (in hun volgorde), daarna *Zonder deelvraag*. `overzicht`
 *  (de bronselectie van spoor J) levert de rol per deelvraag en de open voorstellen; zonder overzicht geldt de
 *  rol van de selectie en zijn er geen voorstellen. */
export function bronnenPerDeelvraag(bronnen: readonly Bronselectie[], actief: readonly Deelvraag[],
  overzicht?: BronselectieOverzicht | null): BronGroep[] {
  const perId = new Map(bronnen.map((b) => [b.id, b]));
  const nummers = new Map<string, number[]>();
  actief.forEach((d, i) => d.bronnen.forEach((sid) => nummers.set(sid, [...(nummers.get(sid) ?? []), i + 1])));
  const hier = new Map((overzicht?.deelvragen ?? []).map((d) => [d.id, d]));

  const groepen: BronGroep[] = actief.map((d, i) => {
    const o = hier.get(d.id);
    const rolHier = new Map((o?.bronnen ?? []).map((b) => [b.selectie_id, b.rol]));
    return {
      deelvraag: { id: d.id, nr: i + 1, vraag: d.vraag },
      bronnen: d.bronnen.flatMap((sid) => {
        const s = perId.get(sid);
        return s ? [{ selectie: s, rol: rolHier.get(sid) ?? s.rol, ook: (nummers.get(sid) ?? []).filter((n) => n !== i + 1) }] : [];
      }),
      voorstellen: (o?.kandidaten ?? []).filter((k) => k.stand === "voorgesteld")
        .map((k) => ({ id: k.id, bron_iri: k.bron_iri, label: k.label })),
    };
  });
  const zonder = bronnen.filter((b) => !nummers.has(b.id));
  if (zonder.length || !actief.length) {
    groepen.push({ deelvraag: null, bronnen: zonder.map((s) => ({ selectie: s, rol: s.rol, ook: [] })), voorstellen: [] });
  }
  return groepen;
}

/** Laat in elke groep alleen wat bij `past` hoort; een groep die daardoor leeg raakt, valt weg. Zonder filter
 *  blijft een lege deelvraag staan: dan is zichtbaar dat er nog niets bij hoort. */
export function filterGroepen(groepen: readonly BronGroep[], past: (b: BronInGroep) => boolean, gefilterd: boolean): BronGroep[] {
  if (!gefilterd) return [...groepen];
  return groepen.map((g) => ({ ...g, bronnen: g.bronnen.filter(past), voorstellen: [] }))
    .filter((g) => g.bronnen.length > 0);
}

/** Het aantal verschillende bronnen over de groepen heen (een bron bij twee deelvragen telt één keer). */
export function uniekeBronnen(groepen: readonly BronGroep[]): number {
  return new Set(groepen.flatMap((g) => g.bronnen.map((b) => b.selectie.id))).size;
}

/** Begint een stuk label met een plek in een regeling ("Artikel 9", "Hoofdstuk V", "art. 3.1")? */
const PLEK = /^(artikel|art\.|lid|onderdeel|hoofdstuk|afdeling|paragraaf|subparagraaf|titeldeel|titel\s+\d|divisie|bepaling|bijlage|boek|deel\s+\d)/i;

/** Een label als bepaling en regeling, voor een rij zoals in de mock-up: de bepaling als titel, de regeling
 *  eronder. Twee vormen komen voor: van Lex "Artikel 9, lid 1 – Invorderingswet 1990" (regeling achteraan) en van
 *  de api "Invorderingswet 1990 – Artikel 9, Lid 1" (regeling vooraan, soms met een opschrift erachter). */
export function bepalingEnRegeling(label: string): { bepaling: string; regeling: string } {
  const delen = label.split(" – ").map((d) => d.trim()).filter(Boolean);
  if (delen.length < 2) return { bepaling: label, regeling: "" };
  if (PLEK.test(delen[0])) return { bepaling: delen.slice(0, -1).join(" – "), regeling: delen[delen.length - 1] };
  if (PLEK.test(delen[1])) return { bepaling: delen.slice(1).join(" – "), regeling: delen[0] };
  return { bepaling: label, regeling: "" };
}

/** "ook bij deelvraag 2", "ook bij deelvragen 2 en 3"; leeg als de bron alleen hier hoort. */
export function ookBijZin(ook: readonly number[]): string {
  if (!ook.length) return "";
  if (ook.length === 1) return `ook bij deelvraag ${ook[0]}`;
  return `ook bij deelvragen ${ook.slice(0, -1).join(", ")} en ${ook[ook.length - 1]}`;
}
