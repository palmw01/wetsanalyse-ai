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

/** Kleur draagt hier een oordeel: gedekt groen, half geel, niets neutraal – met tekst erbij. */
export const STAND_KLASSE: Record<DeelvraagStand, string> = {
  gedekt: "border-aandacht-groen-rand bg-aandacht-groen-bg text-aandacht-groen-tekst",
  geen_begrip: "border-aandacht-geel-rand bg-aandacht-geel-bg text-aandacht-geel-tekst",
  geen_bron: "border-line bg-surface text-muted",
};

/** Actieve deelvragen in hun volgorde, de voorstellen van Lex apart. */
export function splits(deelvragen: Deelvraag[] | undefined): { actief: Deelvraag[]; voorgesteld: Deelvraag[] } {
  const lijst = [...(deelvragen ?? [])].sort((a, b) => a.volgorde - b.volgorde || a.aangemaakt.localeCompare(b.aangemaakt));
  return { actief: lijst.filter((d) => d.status === "actief"), voorgesteld: lijst.filter((d) => d.status === "voorgesteld") };
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
