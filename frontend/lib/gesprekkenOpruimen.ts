// De teksten van het opruimen in de instellingen (tab Gesprekken). Pure helpers, zodat vitest ze toetst.

/** "Geen gesprekken", "1 gesprek", "71 gesprekken". */
export function aantalGesprekken(n: number): string {
  if (n === 0) return "Geen gesprekken";
  return n === 1 ? "1 gesprek" : `${n} gesprekken`;
}

/** De tweede stand van de verwijderknop: hij zegt hoeveel er weggaat. */
export function bevestigVerwijderen(n: number): string {
  return `${aantalGesprekken(n)} verwijderen?`;
}

/** De melding na afloop. */
export function uitkomstZin(handeling: "verwijderd" | "gearchiveerd", n: number): string {
  if (n === 0) return handeling === "verwijderd" ? "Er was niets te verwijderen." : "Er was niets te archiveren.";
  return `${aantalGesprekken(n)} ${handeling}.`;
}
