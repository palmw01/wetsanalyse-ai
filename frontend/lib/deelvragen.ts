import type { Deelvraag, DeelvraagStand, DeelvragenDekking } from "./types";

/** Deelvragen bij een werkgebied (optioneel; open keuze 4). De rekenkern van `Deelvragen.tsx`. */

export const STAND_LABEL: Record<DeelvraagStand, string> = {
  gedekt: "Gedekt",
  geen_begrip: "Nog geen geaccordeerd begrip",
  geen_bron: "Nog geen bron",
};

export const STAND_UITLEG: Record<DeelvraagStand, string> = {
  gedekt: "Er hoort minstens één geaccordeerd begrip bij deze deelvraag.",
  geen_begrip: "Er horen bronnen of begrippen bij, maar nog geen geaccordeerd begrip.",
  geen_bron: "Er hoort nog geen bron en geen begrip bij deze deelvraag.",
};

/** Kleur draagt hier een oordeel: gedekt groen, half geel, niets neutraal – met tekst erbij
 *  (`StatusLabel`). */
export const STAND_TOON: Record<DeelvraagStand, "groen" | "geel" | "neutraal"> = {
  gedekt: "groen",
  geen_begrip: "geel",
  geen_bron: "neutraal",
};

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

/** "2 van 3 deelvragen gedekt"; leeg zonder deelvragen. */
export function dekkingZin(d: DeelvragenDekking | null): string {
  if (!d || d.totaal === 0) return "";
  return `${d.telling.gedekt} van ${d.totaal} ${d.totaal === 1 ? "deelvraag" : "deelvragen"} gedekt`;
}

/** Klopt de vorm? Een api zonder deelvragen (of een mock) antwoordt anders; dan geen dekking tonen. */
export function isDeelvragenDekking(v: unknown): v is DeelvragenDekking {
  const d = v as DeelvragenDekking | null;
  return !!d && Array.isArray(d.deelvragen) && typeof d.totaal === "number" && !!d.telling;
}

/** Een id aan of uit een set zetten, in de volgorde waarin hij stond. */
export function wissel(ids: readonly string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}

/** Twee sets gelijk, ongeacht de volgorde: dan valt er niets op te slaan. */
export function zelfdeSet(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((x) => b.includes(x));
}
