import type { Deelvraag } from "./types";

/** Deelvragen bij een werkgebied (optioneel; open keuze 4). De rekenkern van `Deelvragen.tsx`. Hun stand is de
 *  voortgang van de bronselectie (`deelvraagStand` in `lib/bronselectie.ts`, spoor K). */

/** Actieve deelvragen in hun volgorde, de voorstellen van Lex apart. */
export function splits(deelvragen: Deelvraag[] | undefined): { actief: Deelvraag[]; voorgesteld: Deelvraag[] } {
  const lijst = [...(deelvragen ?? [])].sort((a, b) => a.volgorde - b.volgorde || a.aangemaakt.localeCompare(b.aangemaakt));
  return { actief: lijst.filter((d) => d.status === "actief"), voorgesteld: lijst.filter((d) => d.status === "voorgesteld") };
}

/** De voorstellen van Lex die deze deelvraag zouden vervangen (herformulering of splitsing, F3d). */
export function voorstellenVoor(deelvraagId: string, deelvragen: readonly Deelvraag[] | undefined): Deelvraag[] {
  return (deelvragen ?? []).filter((d) => d.status === "voorgesteld" && d.vervangt === deelvraagId);
}

/** "vervangt “…”" bij een voorstel; leeg als het niets vervangt of de oude er niet (meer) staat. */
export function vervangtZin(voorstel: Deelvraag, deelvragen: readonly Deelvraag[] | undefined): string {
  const oud = voorstel.vervangt && (deelvragen ?? []).find((d) => d.id === voorstel.vervangt);
  return oud ? `Vervangt “${oud.vraag}”` : "";
}

/** Na overnemen: wat de melding zegt. */
export function overgenomenZin(voorstel: Deelvraag, deelvragen: readonly Deelvraag[] | undefined): string {
  return vervangtZin(voorstel, deelvragen)
    ? "Deelvraag vervangen; haar bronnen en begrippen gingen mee." : "Deelvraag overgenomen.";
}

/** Een id aan of uit een set zetten, in de volgorde waarin hij stond. */
export function wissel(ids: readonly string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}

/** Twee sets gelijk, ongeacht de volgorde: dan valt er niets op te slaan. */
export function zelfdeSet(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((x) => b.includes(x));
}

/** Eén regel in de bewerkstand van het blok Deelvragen: een bestaande deelvraag (`id`), of een nieuwe zonder id.
 *  `weg`: verwijderd in de bewerkstand, pas definitief bij *Opslaan* (besluit gebruiker 5 nov 2026). */
export interface DeelvraagConcept { id?: string; vraag: string; weg?: boolean }

export type DeelvraagStap =
  | { soort: "verwijder"; id: string }
  | { soort: "wijzig"; id: string; vraag: string }
  | { soort: "nieuw"; vraag: string };

/** Het begin van de bewerkstand: de actieve deelvragen in hun volgorde. */
export function conceptVan(actief: readonly Pick<Deelvraag, "id" | "vraag">[]): DeelvraagConcept[] {
  return actief.map((d) => ({ id: d.id, vraag: d.vraag }));
}

/** Wat *Opslaan* doet, in deze volgorde: eerst verwijderen, dan wijzigen, dan toevoegen. Zo botst een nieuwe vraag
 *  niet met de tekst van een vraag die net weggaat (de api weigert dezelfde vraag twee keer). Een lege nieuwe regel
 *  telt niet; een ongewijzigde vraag ook niet. Een id dat intussen niet meer bestaat (een collega verwijderde haar),
 *  komt nooit als nieuwe deelvraag terug. */
export function deelvraagStappen(oud: readonly Pick<Deelvraag, "id" | "vraag">[], concept: readonly DeelvraagConcept[]): DeelvraagStap[] {
  const was = new Map(oud.map((d) => [d.id, d.vraag]));
  const verwijder: DeelvraagStap[] = [], wijzig: DeelvraagStap[] = [], nieuw: DeelvraagStap[] = [];
  for (const c of concept) {
    const vraag = c.vraag.trim();
    if (c.id && was.has(c.id)) {
      if (c.weg) verwijder.push({ soort: "verwijder", id: c.id });
      else if (vraag !== (was.get(c.id) ?? "").trim()) wijzig.push({ soort: "wijzig", id: c.id, vraag });
    } else if (!c.id && !c.weg && vraag) nieuw.push({ soort: "nieuw", vraag });
  }
  return [...verwijder, ...wijzig, ...nieuw];
}

/** De stappen als één aanroep: de api legt ze samen vast, alles-of-niets en in één revisie. */
export function deelvragenSamen(stappen: readonly DeelvraagStap[]) {
  return {
    verwijderen: stappen.flatMap((s) => s.soort === "verwijder" ? [s.id] : []),
    wijzigen: stappen.flatMap((s) => s.soort === "wijzig" ? [{ id: s.id, vraag: s.vraag }] : []),
    nieuw: stappen.flatMap((s) => s.soort === "nieuw" ? [s.vraag] : []),
  };
}

/** Waarom *Opslaan* (nog) niet kan: een bestaande deelvraag leeggemaakt. Verwijderen doe je met de prullenbak, zodat
 *  een leeg veld nooit stil een deelvraag met haar bronselectie weghaalt. */
export function conceptFout(concept: readonly DeelvraagConcept[]): string | null {
  return concept.some((c) => c.id && !c.weg && !c.vraag.trim())
    ? "Een deelvraag is leeg. Vul haar in, of verwijder haar met de prullenbak." : null;
}
