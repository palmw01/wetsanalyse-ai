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
