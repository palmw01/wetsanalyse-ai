// Het concept van de vraag per gesprek (UI-08). Wie half getypt naar een ander gesprek gaat, of de werkplek opnieuw
// opent, vindt zijn vraag terug. Het chatvenster remount bij elke wissel (`WorkbenchShell`, `key={mountKey}`), dus de
// invoer kan niet in React-state blijven.
//
// Bewust `sessionStorage`: een concept hoort bij dit tabblad, niet bij de computer, en niet in de api. Elke lees- en
// schrijfactie zit in try/catch: zonder opslag (privévenster, geblokkeerd, server-render) werkt de pagina gewoon, alleen
// zonder concept.

const VOORVOEGSEL = "lex.concept.";

/** Een gesprek dat nog geen id heeft (het nieuwe gesprek) heeft één concept. */
export function conceptSleutel(gesprekId: string | null): string {
  return VOORVOEGSEL + (gesprekId ?? "nieuw");
}

export function leesConcept(gesprekId: string | null): string {
  try {
    return window.sessionStorage.getItem(conceptSleutel(gesprekId)) ?? "";
  } catch {
    return "";
  }
}

/** Een lege of witte tekst wist het concept: na versturen staat er niets meer klaar. */
export function bewaarConcept(gesprekId: string | null, tekst: string): void {
  try {
    if (tekst.trim()) window.sessionStorage.setItem(conceptSleutel(gesprekId), tekst);
    else window.sessionStorage.removeItem(conceptSleutel(gesprekId));
  } catch {
    // Geen opslag: het concept geldt dan alleen zolang dit venster openstaat.
  }
}
